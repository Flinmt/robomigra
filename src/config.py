import os
from dotenv import load_dotenv

load_dotenv()

import platform

class Config:
    _default_driver = '{SQL Server}'
    if platform.system() != 'Windows':
        _default_driver = '{ODBC Driver 17 for SQL Server}'

    _env_driver = os.getenv('DB_DRIVER', _default_driver)

    # Correção Automática para Linux/Docker
    # Se estiver rodando no Linux mas a config vier como o driver legado do Windows, ajustamos.
    if platform.system() != 'Windows' and _env_driver == '{SQL Server}':
        print(f"⚠️  Aviso: Driver '{_env_driver}' não suportado no Linux. Alternando automaticamente para 'ODBC Driver 17 for SQL Server'.")
        _env_driver = '{ODBC Driver 17 for SQL Server}'

    DB_CONNECTION_STRING = (
        f"DRIVER={_env_driver};"
        f"SERVER={os.getenv('DB_SERVER')};"
        f"DATABASE={os.getenv('DB_DATABASE')};"
        f"UID={os.getenv('DB_UID')};"
        f"PWD={os.getenv('DB_PWD')};"
        "Trusted_Connection=no;"
    )
    
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', 5))
    SLEEP_BATCH = float(os.getenv('SLEEP_BATCH', 60.0))
    SLEEP_PATIENT = float(os.getenv('SLEEP_PATIENT', 5.0))
    CHECK_OPERATING_HOURS = os.getenv('CHECK_OPERATING_HOURS', 'true').lower() == 'true'
