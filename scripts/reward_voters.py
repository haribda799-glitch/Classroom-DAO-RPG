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

VOTER_CONTRACT_ADDRESS = "0xD9414F3EafCd6a30EaaD5366F8767194C9D5e0A3"
TOKEN_CONTRACT_ADDRESS = "0x1731F7F26F6ff2B79A9a5f9C86B6Fec319B7e6E2"

VOTERS = [
    "0xee6ee154ff4a3Ded3cf83102142df09447bf897c",  # Voter 1
    "0xB7C4E160D0aFD3e547aaB59c388182766E9eFA7e",  # Voter 2
    "0xA59024433a69e05Ee48E07A7727044a78622961C"   # Voter 3
]

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
    print(f"\nОтправитель наград (Chairperson): {chairperson.address}")
    
    # Загружаем контракты
    print("\nЗагрузка контрактов...")
    voter_contract = boa.load_partial("Voter.vy").at(VOTER_CONTRACT_ADDRESS)
    token_contract = boa.load_partial("contracts/Token.vy").at(TOKEN_CONTRACT_ADDRESS)
    
    # Получаем победителя
    winning_idx = voter_contract.winning_proposal()
    winner_name = voter_contract.winner_name()
    print(f"\n🏆 Победило предложение #{winning_idx}: {winner_name}")
    
    # Сумма вознаграждения
    REWARD_AMOUNT = 500 * 10**18
    
    print("\nПроверка избирателей...")
    winners = []
    
    for i, voter_address in enumerate(VOTERS):
        print(f"\n--- Voter {i+1} ({voter_address}) ---")
        
        # Получаем данные избирателя (в Vyper 0.4 struct возвращается как tuple)
        # Struct Voter: (weight, voted, delegate, vote)
        voter_data = voter_contract.voters(voter_address)
        voted = voter_data[1]
        voted_for = voter_data[3]
        
        if not voted:
            print("  ❌ Не голосовал.")
            continue
            
        print(f"  Голосовал за предложение #{voted_for}")
        
        if voted_for == winning_idx:
            print(f"  🎉 Голос за победителя! Отправка 500 SGC...")
            start_nonce = get_nonce(chairperson.address)
            try:
                # Отправляем токены
                token_contract.transfer(voter_address, REWARD_AMOUNT)
                wait_for_nonce(chairperson.address, start_nonce)
                print("  ✅ Вознаграждение успешно отправлено!")
                winners.append(voter_address)
            except Exception as e:
                print(f"  ❌ Ошибка отправки: {e}")
        else:
            print("  😢 Проголосовал не за победителя, награды нет.")
            
    print("\n=============================================")
    print("Подведение итогов балансов победителей:")
    if not winners:
        print("Нет победителей для отображения.")
    else:
        for w in winners:
            balance = token_contract.balanceOf(w)
            print(f"Адрес: {w} | Баланс: {balance / 10**18:,.2f} SGC")
    print("=============================================")

if __name__ == "__main__":
    main()
