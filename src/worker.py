import pyodbc
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from src.config import Config
from src.database import get_db_connection, IdGenerator
from src.repository import Repository

def run_worker():
    print(f"{'='*80}")
    print(f"🚀 INICIANDO V3.0 - WORKER DE MIGRAÇÃO PROFISSIONAL")
    print(f"📦 Batch Size: {Config.BATCH_SIZE} | 🕒 Sleep Batch: {Config.SLEEP_BATCH}s")
    print(f"⏰ Horário de Funcionamento: ")
    if Config.CHECK_OPERATING_HOURS:
        print(f"   - Fim de Semana: Sex 18h até Seg 05h (Sem Parar)")
        print(f"   - Dias Úteis:    Noite (18h às 05h)")
    else:
        print(f"   - 🟢 RESTRIÇÃO DE HORÁRIO DESATIVADA (Operando 24/7)")
    print(f"{'='*80}\n")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    total_session_migrated = 0
    batch_count = 0

    while True:
        # --- 0. Checagem de Horário (Brasília) ---
        if Config.CHECK_OPERATING_HOURS:
            br_tz = ZoneInfo('America/Sao_Paulo')
            now = datetime.now(br_tz)
            weekday = now.weekday() # 0=Seg, 4=Sex, 5=Sab, 6=Dom
            hour = now.hour

            is_operating = False
            status_msg = ""

            # Lógica de Fim de Semana (Sexta 18h -> Segunda 05h)
            if weekday == 4 and hour >= 18:
                is_operating = True # Sexta a noite
            elif weekday == 5 or weekday == 6:
                is_operating = True # Sábado e Domingo inteiros
            elif weekday == 0 and hour < 5:
                is_operating = True # Segunda madrugada
            
            # Lógica de Dias Úteis (Terça, Quarta, Quinta, Sexta-Madrugada, Segunda-Noite)
            else:
                # Funciona das 18h até as 05h
                if hour >= 18 or hour < 5:
                    is_operating = True
            
            if not is_operating:
                print(f"💤 Fora do horário ({now.strftime('%A %H:%M')} - Brasília). Aguardando turno da noite (18h)...")
                time.sleep(300) 
                continue

        start_time = time.time()
        
        # --- 1. Monitoramento ---
        try:
            stats = Repository.get_stats(cursor)
            print(f"📊 STATUS: Total: {stats[0]} | Migrados: {stats[1]} | Fila Pendente: {stats[2]}")
        except Exception as e:
            print(f"⚠️  Erro ao buscar stats: {e}")

        # --- 1. Busca Lote ---
        try:
            pacientes = Repository.fetch_batch(cursor)
        except Exception as e:
            print(f"⚠️  Erro de Conexão. Reconectando em 10s... ({e})")
            time.sleep(10)
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                continue
            except:
                time.sleep(30)
                continue

        if not pacientes:
            print(f"💤 Fila vazia. Aguardando {Config.SLEEP_BATCH}s... (Total Sessão: {total_session_migrated})")
            time.sleep(Config.SLEEP_BATCH)
            continue

        # --- 2. Processamento ---
        id_gen = IdGenerator(cursor)
        batch_count += 1
        print(f"📦 LOTE #{batch_count} | Pacientes: {len(pacientes)} | Processando...")

        try:
            for cod_paciente in pacientes:
                target_pac_id = int(cod_paciente)
                
                # Busca Imagens
                rows = Repository.fetch_patient_images(cursor, cod_paciente)
                
                # Deduplicação
                unique_imgs = {r.id_imagem_origem: r for r in rows}
                valid_rows = list(unique_imgs.values())

                if not valid_rows:
                    continue

                # --- 3. Inserção Atômica por Paciente ---
                Repository.toggle_identity(cursor, "tbllaudoimagem", "ON")
                
                saved_count = 0
                dates_migrated = set()
                
                for row in valid_rows:
                    if not row.blob_data or not row.data_raw:
                        Repository.mark_as_migrated(cursor, row.id_imagem_origem)
                migrated_dates = [] # Changed to list to collect all dates for logging
                
                # --- 2.2. Agrupamento Inteligente ---
                # Chave de Agrupamento: (Código Procedimento, Data Dia)
                # Objetivo: Unificar múltiplas imagens do mesmo exame/dia em um único Atendimento
                grouped_images = {}
                
                for img in valid_rows:
                    # img = (id_origem, blob, ext, data_full, cod_proc, nome_proc, cod_pac)
                    # Extrai apenas a DATA (Ignora Hora) para agrupar
                    data_dia = img.data_raw.date() if img.data_raw else datetime.min.date()
                    key = (img.cod_proc, data_dia)
                    
                    if key not in grouped_images:
                        grouped_images[key] = {
                            'header': img, # Usa os dados da primeira imagem como cabeçalho
                            'items': []
                        }
                    grouped_images[key]['items'].append(img)

                # --- 2.3. Migração dos Grupos ---
                for key, group in grouped_images.items():
                    header_img = group['header']
                    items = group['items']
                    
                    # Skip if header data is missing
                    if not header_img.blob_data or not header_img.data_raw:
                        for item_img in items:
                            Repository.mark_as_migrated(cursor, item_img.id_imagem_origem)
                        continue

                    # Gera IDs MESTRES (Para o grupo inteiro)
                    atend_id = id_gen.get_atendimento_id_by_client(target_pac_id)
                    fatura_id = id_gen.next_global_fatura_id()
                    # REGRA: ID Laudo Cliente DEVE ser igual ao ID Fatura Atendimento
                    laudo_cli_id = fatura_id 
                    
                    # LOG DETALHADO (Solicitado pelo Usuário)
                    data_fmt = header_img.data_raw.strftime('%d/%m/%Y')
                    print(f"   ► Grupo: Proc {header_img.cod_proc} em {data_fmt} ({len(items)} imgs) -> AtendID: {atend_id} | FatID: {fatura_id}")

                    # Insert 1: Atendimento (Pai)
                    cursor.execute("""
                        INSERT INTO tblatendimento (
                            intAtendimentoId, datAtende, intProfissionalId, intClienteId, 
                            intEmpresaId, intUsuarioId, datAtendimento, strStatus, bolCheck, intTipoAtendimentoId
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (atend_id, header_img.data_raw, 1, target_pac_id, 1, 61, header_img.data_raw, 'FECHADO', 'T', 2))

                    # Insert 2: Fatura (Filho)
                    cursor.execute("""
                        INSERT INTO tblfaturaatendimento (
                            intFaturaAtendimentoId, intClienteId, intAtendimentoId, 
                            strProcedimento, strDescrProcedimento, numQuantidade, numValor, 
                            intEmpresaId, intUsuarioId, datFaturaAtendimento, strStatusFat
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (fatura_id, target_pac_id, atend_id, header_img.cod_proc, header_img.nome_proc, 1.0, 0.0, 1, 61, header_img.data_raw, 'FECHADO'))

                    # Insert 3: Laudo Cliente (Neto)
                    cursor.execute("""
                        INSERT INTO tbllaudocliente (
                           intLaudoClienteId, intClienteId, intAtendimentoId, intFaturaAtendimentoId,
                           strCodigoProcedimento, strDescrProcedimento, 
                           strStatus, intMedicoId, intUsuarioId, intEmpresaId,
                           datLaudoCliente, datLiberacao, bolCheck, bolConcluido
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        laudo_cli_id, target_pac_id, atend_id, fatura_id,
                        header_img.cod_proc, header_img.nome_proc,
                        'ASSINADO', 1, 61, 1,
                        header_img.data_raw, header_img.data_raw, None, None
                    ))

                    # Insert 4: Imagens (Bisnetos - Loop interno)
                    for info_img in items:
                        # Skip if image data is missing
                        if not info_img.blob_data or not info_img.data_raw:
                            Repository.mark_as_migrated(cursor, info_img.id_imagem_origem)
                            continue

                        img_id = id_gen.next_global_img_id()
                        fn = f"{header_img.cod_proc}-{fatura_id}-{str(uuid.uuid4())[:4]}.{info_img.extensao}"
                        
                        cursor.execute("""
                            INSERT INTO tbllaudoimagem (
                                intLaudoImagemId, strLaudoImagem, intClienteId, intAtendimentoId, intFaturaAtendimentoId, 
                                strCodigoProcedimento, strDescrProcedimento, intOrdem, strTerminal, 
                                imgImagem, intUsuarioId, intEmpresaId, datLaudoImagem, bolImpressao, intLaudoClienteId
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            img_id, fn, target_pac_id, atend_id, fatura_id,
                            header_img.cod_proc, header_img.nome_proc, 0, 'MIGRACAO', 
                            pyodbc.Binary(info_img.blob_data), 61, 1, header_img.data_raw, 'N', laudo_cli_id
                        ))

                        # Marca cada imagem individualmente como migrada
                        Repository.mark_as_migrated(cursor, info_img.id_imagem_origem)
                        saved_count += 1
                        
                        # Coleta data para log
                        if info_img.data_raw:
                            migrated_dates.append(info_img.data_raw.strftime('%m/%Y'))
                
                Repository.toggle_identity(cursor, "tbllaudoimagem", "OFF")
                
                dates_str = ", ".join(sorted(list(set(migrated_dates)))) # Use set for unique dates in log
                print(f"   ✅ Paciente {cod_paciente}: {saved_count} imagens migradas. [Ref: {dates_str}]")
                total_session_migrated += saved_count
                time.sleep(Config.SLEEP_PATIENT)

            conn.commit()
            elapsed = time.time() - start_time
            print(f"   ⏱️  Lote em {elapsed:.2f}s. Pausa de {Config.SLEEP_BATCH}s...")
            time.sleep(Config.SLEEP_BATCH)

        except Exception as e:
            conn.rollback()
            print(f"\n❌ ERRO NO LOTE: {e}")
            Repository.toggle_identity(cursor, "tbllaudoimagem", "OFF")
            time.sleep(5)
