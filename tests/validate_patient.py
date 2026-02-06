import pyodbc
from src.database import get_db_connection
from src.repository import Repository

def validate_patient(patient_id):
    print(f"🔍 Validating Patient {patient_id}...")
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Check Source Data (tblmigracao + img_rcl)
    # Get ALL items for this patient, regardless of migration status
    sql_source = """
        SELECT 
            m.strCodigo as id_imagem_origem,
            m.strextensao as extensao,
            m.strCodigoPaciente,
            i.IMG_RCL_RCL_DTHR as data_raw
        FROM tblmigracao m WITH (NOLOCK)
        INNER JOIN img_rcl i WITH (NOLOCK) ON m.strCodigo = CAST(i.IMG_RCL_IND AS VARCHAR(50))
        WHERE m.strCodigoPaciente = ?
    """
    cursor.execute(sql_source, (patient_id,))
    source_items = cursor.fetchall()
    
    print(f"\n📂 SOURCE DATA (tblmigracao): Found {len(source_items)} items for patient {patient_id}")
    if not source_items:
        print("   ❌ No data found in source table for this patient found.")
        return

    source_ids = {row.id_imagem_origem: row for row in source_items}
    
    if len(source_items) != len(source_ids):
        print(f"   ⚠️  DUPLICATES FOUND: {len(source_items)} rows vs {len(source_ids)} unique IDs.")
        # Find duplicates
        id_counts = {}
        for row in source_items:
            id_counts[row.id_imagem_origem] = id_counts.get(row.id_imagem_origem, 0) + 1
            
        for img_id, count in id_counts.items():
            if count > 1:
                print(f"      👉 ID {img_id} appears {count} times:")
                # Print details of these rows to see if they are identical
                for r in source_items:
                    if r.id_imagem_origem == img_id:
                        print(f"         - Ext: {r.extensao} | Date: {r.data_raw}")
    
    # 2. Check Control Table (tbl_controle_migracao_python)
    # See which of these source IDs are marked as migrated
    placeholders = ','.join(['?'] * len(source_ids))
    if not placeholders:
        print("   ⚠️ No source IDs to check in control.")
        return

    sql_control = f"""
        SELECT strCodigoImagemOrigem 
        FROM tbl_controle_migracao_python WITH (NOLOCK)
        WHERE strCodigoImagemOrigem IN ({placeholders})
    """
    cursor.execute(sql_control, list(source_ids.keys()))
    migrated_ids = {row[0] for row in cursor.fetchall()}
    
    pending_ids = set(source_ids.keys()) - migrated_ids
    
    print(f"   ✅ Marked as Migrated in Control: {len(migrated_ids)}")
    print(f"   ⏳ Pending in Control: {len(pending_ids)}")
    
    if pending_ids:
        print(f"   ⚠️ WARNING: {len(pending_ids)} items are NOT marked as migrated yet.")
        for pid in list(pending_ids)[:5]:
            print(f"      - Missing: {pid}")
        if len(pending_ids) > 5:
            print(f"      ... and {len(pending_ids) - 5} more.")

    
    # 3. Check Destination Data (tblatendimento -> tblfatura -> tbllaudo -> images/pdfs)
    
    print(f"\n🎯 DESTINATION DATA HIERARCHY:")
    
    # Fetch hierarchy
    # Hierarchy: Atendimento -> Fatura -> LaudoCliente -> (Images U PDFs)
    
    sql_hierarchy = """
        SELECT 
            A.intAtendimentoId,
            A.datAtendimento,
            F.intFaturaAtendimentoId,
            F.strProcedimento,
            L.intLaudoClienteId,
            'IMG' as Tipo,
            LI.intLaudoImagemId as ItemID,
            LI.strLaudoImagem as NomeArquivo,
            LI.datLaudoImagem as DataItem
        FROM tblatendimento A WITH (NOLOCK)
        JOIN tblfaturaatendimento F WITH (NOLOCK) ON F.intAtendimentoId = A.intAtendimentoId AND F.intClienteId = A.intClienteId
        JOIN tbllaudocliente L WITH (NOLOCK) ON L.intFaturaAtendimentoId = F.intFaturaAtendimentoId AND L.intClienteId = A.intClienteId
        JOIN tbllaudoimagem LI WITH (NOLOCK) ON LI.intLaudoClienteId = L.intLaudoClienteId AND LI.intClienteId = A.intClienteId
        WHERE A.intClienteId = ?
        
        UNION ALL
        
        SELECT 
            A.intAtendimentoId,
            A.datAtendimento,
            F.intFaturaAtendimentoId,
            F.strProcedimento,
            L.intLaudoClienteId,
            'PDF' as Tipo,
            LP.intLaudoPDFAnexoId as ItemID,
            'PDF Anexo' as NomeArquivo,
            LP.datLaudoPDFAnexo as DataItem
        FROM tblatendimento A WITH (NOLOCK)
        JOIN tblfaturaatendimento F WITH (NOLOCK) ON F.intAtendimentoId = A.intAtendimentoId AND F.intClienteId = A.intClienteId
        JOIN tbllaudocliente L WITH (NOLOCK) ON L.intFaturaAtendimentoId = F.intFaturaAtendimentoId AND L.intClienteId = A.intClienteId
        JOIN tbllaudopdfanexo LP WITH (NOLOCK) ON LP.intLaudoClienteId = L.intLaudoClienteId AND LP.intClienteId = A.intClienteId
        WHERE A.intClienteId = ?
        
        ORDER BY A.datAtendimento, A.intAtendimentoId, Tipo
    """
    
    cursor.execute(sql_hierarchy, (patient_id, patient_id))
    rows = cursor.fetchall()
    
    if not rows:
        print("   ❌ No structured data found in destination.")
        return

    # Process and Display Tree
    tree = {}
    total_imgs = 0
    total_pdfs = 0
    
    for row in rows:
        # row: (AtendId, DatAtend, FatId, Proc, LaudoId, Tipo, ItemId, Nome, DataItem)
        atend_id = row.intAtendimentoId
        dat_atend = row.datAtendimento
        fat_id = row.intFaturaAtendimentoId
        proc = row.strProcedimento
        laudo_id = row.intLaudoClienteId
        tipo = row.Tipo
        
        if atend_id not in tree:
            tree[atend_id] = {
                'date': dat_atend,
                'faturas': {}
            }
            
        if fat_id not in tree[atend_id]['faturas']:
            tree[atend_id]['faturas'][fat_id] = {
                'proc': proc,
                'laudos': {}
            }
            
        if laudo_id not in tree[atend_id]['faturas'][fat_id]['laudos']:
            tree[atend_id]['faturas'][fat_id]['laudos'][laudo_id] = []
            
        tree[atend_id]['faturas'][fat_id]['laudos'][laudo_id].append({
            'type': tipo,
            'id': row.ItemID,
            'name': row.NomeArquivo,
            'date': row.DataItem
        })
        
        if tipo == 'IMG': total_imgs += 1
        else: total_pdfs += 1

    print(f"   📊 Resumo: {len(tree)} Atendimentos | {total_imgs} Imagens | {total_pdfs} PDFs")
    
    print("\n   🌳 HIERARQUIA DETALHADA:")
    for atend_id, a_data in tree.items():
        date_str = a_data['date'].strftime('%d/%m/%Y') if a_data['date'] else 'Sem Data'
        print(f"   📂 Atendimento {atend_id} ({date_str})")
        
        for fat_id, f_data in a_data['faturas'].items():
            print(f"      🧾 Fatura {fat_id} - Proc: {f_data['proc']}")
            
            for laudo_id, items in f_data['laudos'].items():
                print(f"         📝 Laudo {laudo_id}")
                for item in items:
                    icon = "🖼️ " if item['type'] == 'IMG' else "📄"
                    item_date = item['date'].strftime('%d/%m/%Y') if item['date'] else '?'
                    print(f"            {icon} [{item['type']}] {item['id']} - {item_date}")

    total_dest = total_imgs + total_pdfs
    print(f"\n   🔄 Comparação Final (INDEPENDENTE DO CONTROLE):")
    unique_source_count = len(source_ids)
    print(f"   - Unique Source Items: {unique_source_count}")
    print(f"   - Validated Tree Items: {total_dest}")
    
    if total_dest == unique_source_count:
         print("   ✅ INTEGRITY CONFIRMED: Destination matches Unique Source count exactly.")
    elif total_dest < unique_source_count:
         diff = unique_source_count - total_dest
         print(f"   ❌ DATA LOSS DETECTED: {diff} items are missing in destination!")
         print("      (These items exist in Source but were NOT found in Destination tables)")
    else:
         diff = total_dest - unique_source_count
         print(f"   ⚠️  EXTRA ITEMS: Destination has {diff} more items than source.")
         print("      (Possible duplicates generated during import or manual insertions)")

import sys

# ... previous imports ...

# ... validate_patient function ...

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            pid = int(sys.argv[1])
        else:
            pid = 1115159
        validate_patient(pid)
    except Exception as e:
        print(f"❌ Error: {e}")
