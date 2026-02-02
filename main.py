from src.worker import run_worker

if __name__ == "__main__":
    try:
        run_worker()
    except KeyboardInterrupt:
        print("\n🛑 Worker interrompido pelo usuário.")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
