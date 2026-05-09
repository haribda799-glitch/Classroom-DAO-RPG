import os
import time
import boa
from eth_account import Account
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

if not RPC_URL or not PRIVATE_KEY:
    raise ValueError("Убедитесь, что RPC_URL и PRIVATE_KEY заданы в файле .env")

TOKEN_CONTRACT_ADDRESS = "0x1731F7F26F6ff2B79A9a5f9C86B6Fec319B7e6E2"

def get_nonce(address):
    """Получает текущий подтвержденный Nonce из сети."""
    return int(boa.env._rpc.fetch("eth_getTransactionCount", [address, "latest"]), 16)

def wait_for_nonce(address, expected_nonce):
    """Опрашивает сеть 0G, пока Nonce не превысит expected_nonce."""
    print(f"  ⏳ Ожидание подтверждения (целевой nonce > {expected_nonce})...")
    while True:
        current_nonce = get_nonce(address)
        if current_nonce > expected_nonce:
            break
        time.sleep(2)

def main():
    print("Подключение к сети 0G Galileo Testnet...")
    boa.set_network_env(RPC_URL)
    
    chairperson = Account.from_key(PRIVATE_KEY)
    boa.env.add_account(chairperson)
    boa.env.eoa = chairperson.address
    print(f"Отправитель (Chairperson): {chairperson.address}")
    
    # 1. Деплой нового Voter (Voter V3)
    print("\nРазвертывание нового контракта Voter...")
    proposals = ["Alice", "Bob", "Charlie", "David"]
    
    start_nonce = get_nonce(chairperson.address)
    voter_contract = boa.load("Voter.vy", proposals, TOKEN_CONTRACT_ADDRESS)
    wait_for_nonce(chairperson.address, start_nonce)
    print(f"\033[1m✅ Voter V3 развернут по адресу: {voter_contract.address}\033[0m")
    
    # 2. Получаем контракт SGC Token
    print("\nЗагрузка смарт-контракта SGC...")
    token_contract = boa.load_partial("contracts/Token.vy").at(TOKEN_CONTRACT_ADDRESS)
    
    # 3. Выдаем Approve (разрешение) новому Voter на снятие SGC с нашего кошелька
    APPROVE_AMOUNT = 1_000_000 * 10**18
    print(f"\nВыдача разрешения (Approve) контракту Voter ({voter_contract.address}) на сумму 1,000,000 SGC...")
    
    start_nonce = get_nonce(chairperson.address)
    token_contract.approve(voter_contract.address, APPROVE_AMOUNT)
    wait_for_nonce(chairperson.address, start_nonce)
    print("  ✅ Approve успешно выдан!")
    
    print("\n=============================================")
    print("Установка V3 завершена!")
    print(f"Новый адрес Voter: {voter_contract.address}")
    print("Не забудьте обновить VOTER_ADDRESS в frontend/index.html")
    print("=============================================")

if __name__ == "__main__":
    main()
