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
ALICE_VOTER = "0xAb2615a0D3703c3Afad234E1Ab74846e73f09230"

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
    
    # Настраиваем аккаунт председателя (мы будем отправлять с него SGC)
    chairperson = Account.from_key(PRIVATE_KEY)
    boa.env.add_account(chairperson)
    boa.env.eoa = chairperson.address
    print(f"\nОтправитель (Chairperson): {chairperson.address}")
    
    # Загружаем контракт SGC Token
    print("\nЗагрузка смарт-контракта SGC...")
    token_contract = boa.load_partial("contracts/Token.vy").at(TOKEN_CONTRACT_ADDRESS)
    
    REWARD_AMOUNT = 500 * 10**18
    print(f"\nОтправка 500 SGC на адрес избирателя Алисы: {ALICE_VOTER}")
    
    start_nonce = get_nonce(chairperson.address)
    try:
        # Отправляем токены
        token_contract.transfer(ALICE_VOTER, REWARD_AMOUNT)
        wait_for_nonce(chairperson.address, start_nonce)
        print("  ✅ Вознаграждение успешно отправлено!")
    except Exception as e:
        print(f"  ❌ Ошибка отправки: {e}")
        return

    print("\n=============================================")
    balance_wei = token_contract.balanceOf(ALICE_VOTER)
    balance_formatted = balance_wei / 10**18
    print(f"Финальный баланс {ALICE_VOTER}: {balance_formatted:,.2f} SGC")
    print("=============================================")

if __name__ == "__main__":
    main()
