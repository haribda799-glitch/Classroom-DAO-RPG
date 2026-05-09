import os
import boa
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

if not RPC_URL or not PRIVATE_KEY:
    raise ValueError("Убедитесь, что RPC_URL и PRIVATE_KEY заданы в файле .env")

# Адрес задеплоенного контракта Voter в 0G Galileo
CONTRACT_ADDRESS = "0xD9414F3EafCd6a30EaaD5366F8767194C9D5e0A3"

def main():
    from eth_account import Account
    
    print("Подключение к сети 0G Galileo Testnet...")
    boa.set_network_env(RPC_URL)
    
    print("Инициализация аккаунта...")
    account = Account.from_key(PRIVATE_KEY)
    boa.env.add_account(account)
    boa.env.eoa = account.address
    print(f"Текущий аккаунт (EOA): {boa.env.eoa}")
    
    print(f"Загрузка контракта по адресу: {CONTRACT_ADDRESS}...")
    
    # Чтобы использовать загрузку по адресу без Etherscan ABI (т.к. мы знаем исходник),
    # мы загружаем контракт на основе локального Vyper файла
    # load_partial() позволяет нам скомпилировать ABI локально и привязать к live-адресу
    voter_contract = boa.load_partial("Voter.vy").at(CONTRACT_ADDRESS)
    
    # 1. Загружаем chairperson
    chairperson = voter_contract.chairperson()
    print(f"Chairperson: {chairperson}")
    
    # 2. Вызываем proposals(0)
    proposal_0 = voter_contract.proposals(0)
    # proposals(0) возвращает структуру: (name, voteCount)
    original_name = proposal_0[0]
    
    print("-" * 40)
    print(f"Предложение #0: {original_name}")
    print(f"Количество голосов: {proposal_0[1]}")
    print("-" * 40)
    
    if original_name == "Alice":
        print("✅ Данные в блокчейне соответствуют деплою!")
    else:
        print("❌ Имя предложения не сходится.")
        
    print("\nОтправка транзакции голосования...")
    try:
        voter_contract.vote(0)
        print("✅ Голос успешно учтен!")
    except Exception as e:
        if "Already voted" in str(e):
            print("Вы уже проголосовали, повторное действие заблокировано контрактом")
        else:
            print(f"❌ Произошла ошибка при голосовании: {e}")
            
    print("\nОбновление данных...")
    updated_proposal_0 = voter_contract.proposals(0)
    
    print("-" * 40)
    print(f"Предложение #0: {updated_proposal_0[0]}")
    print(f"Финальное количество голосов: {updated_proposal_0[1]}")
    print("-" * 40)

if __name__ == "__main__":
    main()
