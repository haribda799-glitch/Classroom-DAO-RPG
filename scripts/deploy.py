import os
import boa
from eth_account import Account
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

if not RPC_URL or not PRIVATE_KEY:
    raise ValueError("Убедитесь, что RPC_URL и PRIVATE_KEY заданы в файле .env")

def main():
    print("Подключение к сети 0G Galileo Testnet...")
    
    # Подключаемся к RPC (Titanoboa автоматически определит Chain ID через provider)
    boa.set_network_env(RPC_URL)
    
    # Загружаем аккаунт деплоера из приватного ключа
    account = Account.from_key(PRIVATE_KEY)
    boa.env.add_account(account)
    
    # Опционально: убедимся, что по умолчанию транзакции идут с этого аккаунта
    boa.env.eoa = account.address
    
    print(f"Аккаунт деплоера: {account.address}")
    
    # Исходные имена предложений
    NAMES = ["Alice", "Bob", "Charlie"]
    
    print("Выполняется компиляция и деплой Voter.vy...")
    
    # Компилируем и отправляем транзакцию на деплой
    voter_contract = boa.load("Voter.vy", NAMES)
    
    address = voter_contract.address
    
    print("\n✅ Деплой успешно завершен!")
    print(f"Адрес контракта: {address}")
    print(f"Ссылка на эксплорер: https://testnet.0g.ai/address/{address}")

if __name__ == "__main__":
    main()
