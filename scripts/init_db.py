import asyncio
import sys
import os

# Setup de path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.infrastructure.database import create_tables, engine

async def init():
    print("🏗️  Criando tabelas no banco de dados...")
    try:
        await create_tables()
        print("✅ Tabelas criadas com sucesso (Doctors, ShiftSlots, RosterSolutions).")
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init())