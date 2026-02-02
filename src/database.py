import pyodbc
from src.config import Config

def get_db_connection():
    """
    Estabelece uma conexão nova com o banco de dados.
    Configura timeout infinito (0) para workers de longa duração.
    """
    try:
        conn = pyodbc.connect(Config.DB_CONNECTION_STRING)
        conn.timeout = 0
        return conn
    except Exception as e:
        print(f"❌ Erro fatal de configuração/conexão: {e}")
        raise e

class IdGenerator:
    """
    Gerenciador de IDs com Estratégia de Cache.
    
    Objetivo: Evitar milhares de consultas 'SELECT MAX()' para cada imagem inserida.
    Estratégia: Busca o MAX ID apenas uma vez por lote/ciclo e incrementa localmente na memória.
    """
    def __init__(self, cursor):
        self.cursor = cursor
        # Inicializa o próximo ID disponível baseado no estado atual do banco
        self.last_img_id = self._get_max_id("tbllaudoimagem", "intLaudoImagemId")
        self.last_fat_id = self._get_max_id("tblfaturaatendimento", "intFaturaAtendimentoId")

    def _get_max_id(self, table, pk_column):
        """Busca o maior ID atual de uma tabela usando NOLOCK."""
        sql = f"SELECT ISNULL(MAX({pk_column}), 0) FROM {table} WITH (NOLOCK)"
        self.cursor.execute(sql)
        val = self.cursor.fetchone()[0]
        return val

    def next_global_img_id(self):
        """Retorna o próximo ID único para Tabela de Imagens."""
        self.last_img_id += 1
        return self.last_img_id

    def next_global_fatura_id(self):
        """Retorna o próximo ID único para Faturas."""
        self.last_fat_id += 1
        return self.last_fat_id

    def get_atendimento_id_by_client(self, cliente_id):
        """
        Retorna o ID de Atendimento.
        Nota: Mantém a lógica legada onde o ID parece ser sequencial POR CLIENTE ou depende de contexto específico.
        Não é cacheado globalmente por segurança.
        """
        sql = "SELECT ISNULL(MAX(intAtendimentoId), 0) + 1 FROM tblatendimento WITH (NOLOCK) WHERE intClienteId = ?"
        self.cursor.execute(sql, (cliente_id,))
        return self.cursor.fetchone()[0]
