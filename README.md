# RoboMigra - Professional Migration Worker

RoboMigra is a high-performance Python worker designed to automate the migration of legacy healthcare data (patient records, medical images, and PDF reports) into a modern SQL Server database structure. It ensures data integrity, proper grouping of exams, and operational efficiency by running during specific hours to minimize impact on production systems.

## 🚀 Key Features

*   **Smart Scheduling:** Configurable operating hours (e.g., nights and weekends only) to prevent database overload during business hours (Timezone: `America/Sao_Paulo`).
*   **Batch Processing:** efficient processing of patient records in configurable batch sizes with pause intervals.
*   **Data Deduplication:** Automatically detects and filters duplicate images before migration.
*   **Intelligent Grouping:** Groups multiple images and reports by procedure and date into a single attendance record (*Atendimento*).
*   **Hierarchical Data Insertion:** Maintains referential integrity across multiple related tables (`tblatendimento`, `tblfaturaatendimento`, `tbllaudocliente`, `tbllaudoimagem`, `tbllaudopdfanexo`).
*   **Robust Error Handling:** Transaction management with automatic rollback on failures and auto-reconnection logic.
*   **Dockerized:** Fully containerized for easy deployment and isolation.

## 🛠️ Prerequisites

*   **Python 3.9+**
*   **SQL Server ODBC Driver** (e.g., ODBC Driver 17 for SQL Server)
*   **Docker & Docker Compose** (optional, for containerized execution)

## 📦 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/robomigra.git
    cd robomigra
    ```

2.  **Set up a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration:**
    Copy `.env.example` to `.env` and update the database credentials and worker settings.
    ```bash
    cp .env.example .env
    ```
    *Ensure `DB_SERVER`, `DB_USER`, `DB_PASS`, etc., are correctly set.*

## ▶️ Usage

### Running Locally

To start the worker directly on your machine:

```bash
python main.py
```

### Running with Docker

For a production-ready isolated environment:

1.  **Build and Start:**
    ```bash
    docker-compose up -d --build
    ```

2.  **View Logs:**
    ```bash
    docker-compose logs -f
    ```

3.  **Stop:**
    ```bash
    docker-compose down
    ```

*> **Note:** If your database is on the host machine, ensure `DB_SERVER` in `.env` is set to `host.docker.internal` when running via Docker.*

## 📂 Project Structure

```
robomigra/
├── src/
│   ├── worker.py       # Main migration logic and optimized loop
│   ├── repository.py   # Database queries and data access layer
│   ├── database.py     # Connection management and ID generation
│   └── config.py       # Configuration loader
├── main.py             # Application entry point
├── Dockerfile          # Docker image definition
├── docker-compose.yml  # Docker services configuration
├── requirements.txt    # Python dependencies
└── README.md           # Project documentation
```

## ⚙️ Configuration Options

You can tune the worker behavior in `src/config.py` or via environment variables:

*   `BATCH_SIZE`: Number of patients to process per cycle.
*   `SLEEP_BATCH`: Pause time (in seconds) between batches.
*   `CHECK_OPERATING_HOURS`: Set to `True` to restrict execution to non-business hours.

---
*Developed for efficient and safe medical data migration.*
