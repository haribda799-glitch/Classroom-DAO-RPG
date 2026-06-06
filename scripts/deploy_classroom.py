import os
import time
import boa
from eth_account import Account
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

RPC_URL       = os.getenv("RPC_URL")
PRIVATE_KEY   = os.getenv("PRIVATE_KEY")
TOKEN_ADDRESS = os.getenv("TOKEN_ADDRESS")

if not RPC_URL or not PRIVATE_KEY:
    raise ValueError("Убедитесь, что RPC_URL и PRIVATE_KEY заданы в файле .env")

if not TOKEN_ADDRESS:
    raise ValueError("Убедитесь, что TOKEN_ADDRESS задан в файле .env")


def get_nonce(address):
    """Получает текущий подтверждённый Nonce из сети."""
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
    print(f"Отправитель (Преподаватель): {chairperson.address}")

    # 1. Деплой нового ClassroomDAO
    print("\nРазвертывание нового контракта ClassroomDAO...")
    proposals = ["Web3 Basics", "DeFi", "Smart Contracts", "Cryptography"]

    start_nonce = get_nonce(chairperson.address)
    classroom_contract = boa.load("ClassroomDAO.vy", proposals, TOKEN_ADDRESS)
    wait_for_nonce(chairperson.address, start_nonce)
    print(f"\033[1m✅ ClassroomDAO развернут по адресу: {classroom_contract.address}\033[0m")

    # 2. Получаем контракт SGC Token
    print(f"\nЗагрузка смарт-контракта SGC по адресу {TOKEN_ADDRESS}...")
    token_contract = boa.load_partial("contracts/Token.vy").at(TOKEN_ADDRESS)

    # 3. Выдаём Approve (разрешение) новому ClassroomDAO на снятие SGC
    APPROVE_AMOUNT = 1_000_000 * 10**18
    print(f"\nВыдача разрешения (Approve) контракту ClassroomDAO "
          f"({classroom_contract.address}) на сумму 1,000,000 SGC...")

    start_nonce = get_nonce(chairperson.address)
    token_contract.approve(classroom_contract.address, APPROVE_AMOUNT)
    wait_for_nonce(chairperson.address, start_nonce)
    print("  ✅ Approve успешно выдан!")

    print("\n=============================================")
    print("🎓 Установка ClassroomDAO завершена!")
    print(f"   Новый адрес ClassroomDAO: {classroom_contract.address}")
    print("   Не забудьте обновить VOTER_ADDRESS в frontend/index.html")
    print("=============================================")


if __name__ == "__main__":
    main()
