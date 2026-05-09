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

# Адрес задеплоенного контракта Voter в 0G Galileo
CONTRACT_ADDRESS = "0xD9414F3EafCd6a30EaaD5366F8767194C9D5e0A3"

def get_nonce(address):
    """Получает текущий подтвержденный Nonce из сети."""
    return int(boa.env._rpc.fetch("eth_getTransactionCount", [address, "latest"]), 16)

def wait_for_nonce(address, expected_nonce):
    """
    Опрашивает сеть 0G, пока Nonce аккаунта не превысит expected_nonce.
    Это гарантирует, что отправленная транзакция была включена в блок.
    """
    print(f"  ⏳ Ожидание подтверждения (целевой nonce > {expected_nonce})...")
    while True:
        current_nonce = get_nonce(address)
        if current_nonce > expected_nonce:
            break
        time.sleep(2)

def send_eth_and_wait(sender_address, to_address, amount_wei):
    """
    Утилита для отправки нативного токена A0GI через Titanoboa.
    Использует raw_call(data=b""), корректно обрабатывает 'Unknown format'.
    """
    boa.env.eoa = sender_address
    start_nonce = get_nonce(sender_address)
    
    try:
        # В NetworkEnv это отправит транзакцию, но может выбросить ошибку декодирования пустого ответа
        res = boa.env.raw_call(to_address=to_address, value=amount_wei, data=b"")
        # Попытка преобразовать результат, если это байты
        if isinstance(res, bytes):
            res_hex = res.hex()
            if res_hex:
                print(f"  [Tx] Транзакция отправлена: {res_hex}")
    except Exception as e:
        # Если Titanoboa пытается декодировать b"" и падает - игнорируем
        if "Unknown format" not in str(e):
            raise e
            
    # Ждем, пока nonce увеличится, что означает подтверждение транзакции
    wait_for_nonce(sender_address, start_nonce)

def main():
    print("Подключение к сети 0G Galileo Testnet...")
    boa.set_network_env(RPC_URL)
    
    print("\nИнициализация основного аккаунта (Chairperson)...")
    chairperson = Account.from_key(PRIVATE_KEY)
    boa.env.add_account(chairperson)
    boa.env.eoa = chairperson.address
    print(f"Chairperson EOA: {chairperson.address}")
    
    # Проверка баланса Chairperson:
    chairperson_balance = boa.env.get_balance(chairperson.address)
    print(f"Баланс Chairperson: {chairperson_balance / 10**18:.4f} A0GI")
    if chairperson_balance < 20000000000000000: # 0.02 A0GI
        print("⚠️ ВНИМАНИЕ: Баланс Chairperson меньше 0.02 A0GI, денег на раздачу может не хватить!")
    
    print(f"\nЗагрузка контракта Voter: {CONTRACT_ADDRESS}")
    voter_contract = boa.load_partial("Voter.vy").at(CONTRACT_ADDRESS)
    
    print("\nГенерация 3 новых временных аккаунтов...")
    voters = [Account.create() for _ in range(3)]
    for i, v in enumerate(voters):
        boa.env.add_account(v)
        print(f"  Voter {i+1}: {v.address}")
        
    print("\nРаздача газа (0.005 A0GI) и прав на голосование от Chairperson...")
    GAS_AMOUNT = 5000000000000000 # 0.005 ether in wei
    
    for i, v in enumerate(voters):
        print(f"\n--- Обработка Voter {i+1} ({v.address}) ---")
        
        # 1. Отправляем газ
        print(f"  [Tx Газ] Отправка 0.005 A0GI...")
        try:
            send_eth_and_wait(chairperson.address, v.address, GAS_AMOUNT)
            print(f"  ✅ Газ получен")
        except Exception as e:
            print(f"  ❌ Ошибка перевода: {e}")
            continue # Если нет газа, нет смысла выдавать права и голосовать
            
        # 2. Выдаем право голоса
        boa.env.eoa = chairperson.address
        start_nonce = get_nonce(chairperson.address)
        
        print(f"  [Tx Права] Выдача права голоса...")
        try:
            voter_contract.give_right_to_vote(v.address)
            wait_for_nonce(chairperson.address, start_nonce)
            print("  ✅ Право голоса успешно выдано!")
        except Exception as e:
            print(f"  ❌ Ошибка выдачи прав: {e}")
            
    print("\nГолосование новых аккаунтов...")
    vote_targets = [1, 1, 2]
    proposal_names = ["Alice", "Bob", "Charlie"] # 0, 1, 2
    
    for i, (v, target_idx) in enumerate(zip(voters, vote_targets)):
        print(f"\nГолосует Voter {i+1} за {proposal_names[target_idx]} (Индекс {target_idx})...")
        
        # 3. Проверка баланса перед голосованием
        voter_balance = boa.env.get_balance(v.address)
        print(f"  Баланс избирателя: {voter_balance / 10**18:.4f} A0GI")
        if voter_balance == 0:
            print("  ❌ У избирателя нулевой баланс, транзакция не пройдет!")
            continue

        boa.env.eoa = v.address
        voter_start_nonce = get_nonce(v.address)
        try:
            voter_contract.vote(target_idx)
            wait_for_nonce(v.address, voter_start_nonce)
            print("  ✅ Голос учтен!")
        except Exception as e:
            if "Already voted" in str(e):
                print("  ⚠️ Вы уже проголосовали.")
            elif "Has no right to vote" in str(e):
                print("  ❌ Нет прав на голосование.")
            else:
                print(f"  ❌ Ошибка при голосовании: {e}")
            
    print("\nПодведение итогов...")
    boa.env.eoa = chairperson.address
    
    try:
        winning_idx = voter_contract.winning_proposal()
        winner_name = voter_contract.winner_name()
        
        print("=" * 45)
        print(f"🎉 Победило предложение #{winning_idx}: {winner_name} 🎉")
        print("=" * 45)
    except Exception as e:
        print(f"❌ Ошибка вычисления победителя: {e}")

if __name__ == "__main__":
    main()
