from src.config import Config

class Repository:
    """Centraliza as queries SQL para manter o código limpo."""
    
    @staticmethod
    def get_stats(cursor):
        """Calcula estatísticas de progresso detalhadas (Imgs vs PDFs)."""
        
        # 1. Total Migrado (Separado por Tipo)
        # JOIN com tblmigracao para verificar extensão
        sql_migrated = """
            SELECT 
                SUM(CASE WHEN m.strextensao = 'pdf' THEN 0 ELSE 1 END) as imgs,
                SUM(CASE WHEN m.strextensao = 'pdf' THEN 1 ELSE 0 END) as pdfs
            FROM tbl_controle_migracao_python c WITH (NOLOCK)
            INNER JOIN tblmigracao m WITH (NOLOCK) ON c.strCodigoImagemOrigem = m.strCodigo
        """
        cursor.execute(sql_migrated)
        row_mig = cursor.fetchone()
        mig_imgs = row_mig[0] or 0
        mig_pdfs = row_mig[1] or 0

        # 2. Pendentes Válidos (Separado por Tipo)
        sql_pending = """
            SELECT 
                SUM(CASE WHEN m.strextensao = 'pdf' THEN 0 ELSE 1 END) as imgs_pend,
                SUM(CASE WHEN m.strextensao = 'pdf' THEN 1 ELSE 0 END) as pdfs_pend
            FROM tblmigracao m WITH (NOLOCK)
            WHERE m.strextensao IN ('jpg', 'jpeg', 'png', 'bmp', 'pdf')
            AND NOT EXISTS (
                SELECT 1 FROM tbl_controle_migracao_python C WITH (NOLOCK)
                WHERE C.strCodigoImagemOrigem = m.strCodigo
            )
        """
        cursor.execute(sql_pending)
        row_pend = cursor.fetchone()
        pend_imgs = row_pend[0] or 0
        pend_pdfs = row_pend[1] or 0

        return {
            'migrated_imgs': mig_imgs,
            'migrated_pdfs': mig_pdfs,
            'pending_imgs': pend_imgs,
            'pending_pdfs': pend_pdfs
        }

    @staticmethod
    def fetch_batch(cursor):
        """Busca um lote de pacientes pendentes, priorizando os mais recentes."""
        sql = f"""
            SELECT TOP {Config.BATCH_SIZE} m.strCodigoPaciente
            FROM tblmigracao m WITH (NOLOCK)
            INNER JOIN img_rcl i WITH (NOLOCK) ON m.strCodigo = CAST(i.IMG_RCL_IND AS VARCHAR(50))
            WHERE m.strextensao IN ('jpg', 'jpeg', 'png', 'bmp', 'pdf')
            AND NOT EXISTS (
                SELECT 1 FROM tbl_controle_migracao_python C WITH (NOLOCK)
                WHERE C.strCodigoImagemOrigem = m.strCodigo
            )
            GROUP BY m.strCodigoPaciente
            ORDER BY MAX(i.IMG_RCL_RCL_DTHR) DESC
        """
        cursor.execute(sql)
        return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def fetch_patient_images(cursor, patient_id):
        """Busca todas as imagens pendentes de um paciente específico."""
        sql = """
            SELECT 
                m.strCodigo as id_imagem_origem,
                CAST(m.strBase64 AS VARBINARY(MAX)) as blob_data,
                ISNULL(m.strextensao, 'jpg') as extensao,
                TRY_CONVERT(DATETIME, LEFT(CAST(i.IMG_RCL_RCL_DTHR AS VARCHAR(100)), 19), 120) as data_raw,
                COALESCE(DP.Destino_Codigo, CAST(i.IMG_RCL_RCL_COD AS VARCHAR(50))) as cod_proc,
                COALESCE(P_Novo.strProcedimento, P_Velho.strProcedimento, 'PROCEDIMENTO IMPORTADO') as nome_proc,
                m.strCodigoPaciente as cod_origem
            FROM tblmigracao m WITH (NOLOCK)
            INNER JOIN img_rcl i WITH (NOLOCK) ON m.strCodigo = CAST(i.IMG_RCL_IND AS VARCHAR(50))
            LEFT JOIN tbl_migracao_codigos_depara DP WITH (NOLOCK) ON CAST(i.IMG_RCL_RCL_COD AS VARCHAR(50)) = DP.Origem_Codigo
            LEFT JOIN tblProcedimento P_Novo WITH (NOLOCK) ON P_Novo.strCodigo = DP.Destino_Codigo
            LEFT JOIN tblProcedimento P_Velho WITH (NOLOCK) ON P_Velho.strCodigo = CAST(i.IMG_RCL_RCL_COD AS VARCHAR(50))
            WHERE m.strCodigoPaciente = ? 
            AND m.strextensao IN ('jpg', 'jpeg', 'png', 'bmp', 'pdf')
            AND NOT EXISTS (
                SELECT 1 FROM tbl_controle_migracao_python C WITH (NOLOCK)
                WHERE C.strCodigoImagemOrigem = m.strCodigo
            )
            ORDER BY i.IMG_RCL_RCL_DTHR
        """
        cursor.execute(sql, (patient_id,))
        return cursor.fetchall()

    @staticmethod
    def mark_as_migrated(cursor, image_origin_id):
        cursor.execute("INSERT INTO tbl_controle_migracao_python (strCodigoImagemOrigem) VALUES (?)", (image_origin_id,))

    @staticmethod
    def toggle_identity(cursor, table, status):
        """Helper seguro para ligar/desligar identity insert"""
        try:
            cursor.execute(f"SET IDENTITY_INSERT {table} {status}")
        except Exception:
            pass # Ignora erro se já estiver no estado desejado ou não permitido
