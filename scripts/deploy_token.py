import os
import boa
from eth_account import Account
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

if not RPC_URL or not PRIVATE_KEY:
    raise ValueError("Убедитесь, что RPC_URL и PRIVATE_KEY заданы в файле .env")

def main():
    print("Подключение к сети 0G Galileo Testnet...")
    boa.set_network_env(RPC_URL)
    
    # Настраиваем аккаунт деплоера
    account = Account.from_key(PRIVATE_KEY)
    boa.env.add_account(account)
    boa.env.eoa = account.address
    
    print(f"\nАккаунт деплоера: {account.address}")
    balance = boa.env.get_balance(account.address)
    print(f"Баланс: {balance / 10**18:.4f} A0GI")
    
    if balance == 0:
        raise ValueError("Баланс равен нулю, невозможно оплатить газ.")
    
    print("\nНачинается деплой контракта Token.vy (SGC)...")
    
    # Деплоим контракт
    # В Titanoboa деплой инициируется через .deploy() на загруженном контракте, 
    # либо просто boa.load() в случае работы с локальным файлом.
    token_contract = boa.load("contracts/Token.vy")
    
    token_address = token_contract.address
    print(f"\n=======================================================")
    print(f"✅ УСПЕШНО! Контракт задеплоен.")
    print(f"=======================================================")
    print(f"Адрес токена: {token_address}")
    print(f"Ссылка на 0G Explorer: https://chainscan-galileo.0g.ai/address/{token_address}")
    
    # Чтение данных из контракта
    name = token_contract.name()
    symbol = token_contract.symbol()
    decimals = token_contract.decimals()
    total_supply = token_contract.totalSupply()
    
    print(f"\n--- Метаданные Токена ---")
    print(f"Название: {name}")
    print(f"Символ: {symbol}")
    print(f"Decimals: {decimals}")
    print(f"Total Supply: {total_supply / 10**decimals:,.2f} {symbol}")
    
    print(f"\n--- Импорт токена в MetaMask ---")
    print(f"1. Откройте MetaMask и перейдите в сеть '0G Galileo Testnet'.")
    print(f"2. Прокрутите вниз и нажмите 'Import tokens' (или 'Импорт токенов').")
    print(f"3. Вставьте Адрес контракта токена: {token_address}")
    print(f"4. Символ '{symbol}' и Decimals '{decimals}' должны подтянуться автоматически.")
    print(f"5. Нажмите 'Add Custom Token', вы увидите свои 1,000,000 {symbol}.")

if __name__ == "__main__":
    main()
