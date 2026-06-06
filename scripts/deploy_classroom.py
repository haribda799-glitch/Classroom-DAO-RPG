import argparse
import csv
import os
import sys
import time
import boa
from eth_account import Account
from dotenv import load_dotenv
from pathlib import Path

# Загружаем переменные окружения
load_dotenv()

RPC_URL     = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
TOKEN_ADDRESS = os.getenv("TOKEN_ADDRESS")

if not RPC_URL or not PRIVATE_KEY:
    raise ValueError("Убедитесь, что RPC_URL и PRIVATE_KEY заданы в файле .env")

if not TOKEN_ADDRESS:
    raise ValueError("Убедитесь, что TOKEN_ADDRESS задан в файле .env")

# Размер батча ограничен контрактом (DynArray[address, 20])
BATCH_SIZE   = 20
# Путь к CSV-файлу с экспортом студентов (относительно корня проекта)
EXPORT_CSV   = Path(__file__).parent.parent / "students_export.csv"


def parse_args() -> argparse.Namespace:
    """
    Парсит аргументы командной строки.

    --clean  Режим чистого деплоя: пропускает проверку наличия
             students_export.csv и шаг миграции исторического XP.
    """
    parser = argparse.ArgumentParser(
        description="Деплой ClassroomDAO с опциональной миграцией Legacy XP."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help=(
            "Чистый деплой без миграции XP. "
            "Используйте, если файл students_export.csv недоступен."
        ),
    )
    return parser.parse_args()


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


def load_legacy_xp(csv_path: Path) -> tuple[list[str], list[int]]:
    """
    Читает students_export.csv и возвращает два списка: адреса и XP.

    Формат CSV (с заголовком):
        Nickname,Group,Address,XP,Level

    Пропускает:
      - строки-заголовки и пустые строки;
      - строки с некорректным (не-hex) адресом;
      - строки с отсутствующим или нечисловым XP.
    """
    addresses: list[str] = []
    xp_values: list[int] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = row.get("Address", "").strip()
            xp_raw = row.get("XP", "").strip()

            # Базовая валидация адреса: 0x + 40 hex-символов
            if not addr.startswith("0x") or len(addr) != 42:
                print(f"  ⚠️  Пропущена строка — некорректный адрес: '{addr}'")
                continue

            try:
                int(addr, 16)  # проверяем, что адрес — валидный hex
            except ValueError:
                print(f"  ⚠️  Пропущена строка — адрес не является hex: '{addr}'")
                continue

            # Валидация и преобразование XP
            try:
                xp = int(xp_raw)
                if xp < 0:
                    raise ValueError("XP не может быть отрицательным")
            except ValueError as e:
                print(f"  ⚠️  Пропущена строка (адрес {addr[:10]}…) — {e}")
                continue

            addresses.append(addr)
            xp_values.append(xp)

    return addresses, xp_values


def import_legacy_xp(contract, chairperson_address: str,
                     addresses: list[str], xp_values: list[int]) -> int:
    """
    Разбивает данные на батчи по BATCH_SIZE и вызывает
    batch_import_legacy_xp() для каждого. Возвращает число
    студентов, которым успешно восстановлен опыт.

    Каждый батч ждёт подтверждения через wait_for_nonce()
    прежде чем отправить следующую транзакцию.
    """
    total      = len(addresses)
    imported   = 0
    batch_num  = 0
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE  # ceil division

    print(f"\n  Всего студентов к импорту: {total}")
    print(f"  Будет отправлено батчей:   {num_batches} (по ≤{BATCH_SIZE} за раз)\n")

    for start in range(0, total, BATCH_SIZE):
        batch_num += 1
        end             = start + BATCH_SIZE
        students_batch  = addresses[start:end]
        xp_batch        = xp_values[start:end]
        batch_size_real = len(students_batch)

        print(f"  📦 Батч {batch_num}/{num_batches} "
              f"(строки {start + 1}–{start + batch_size_real})...")

        try:
            nonce_before = get_nonce(chairperson_address)
            contract.batch_import_legacy_xp(students_batch, xp_batch)
            wait_for_nonce(chairperson_address, nonce_before)
            imported += batch_size_real
            print(f"     ✅ Батч {batch_num} подтверждён — "
                  f"восстановлено {batch_size_real} записей.")
        except Exception as exc:
            print(f"     ❌ Батч {batch_num} не прошёл: {exc}")
            print(f"     ⚠️  Пропускаем этот батч и продолжаем...")

    return imported


def main():
    args = parse_args()

    # ── Pre-flight check ──────────────────────────────────────────────────────
    # Выполняется ДО подключения к сети и деплоя, чтобы не тратить газ зря.
    if args.clean:
        print("⚠️  ВНИМАНИЕ: Активирован режим чистого деплоя. "
              "Миграция студентов производиться не будет!")
    else:
        if not EXPORT_CSV.exists():
            sys.exit(
                "🛑 ОШИБКА: Файл students_export.csv не найден! "
                "Деплой отменен. Скачайте выгрузку из Панели Мастера "
                "или используйте флаг --clean для чистого деплоя."
            )
        print(f"✅ Pre-flight: файл '{EXPORT_CSV.name}' найден — миграция XP будет выполнена.")
    # ─────────────────────────────────────────────────────────────────────────

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

    # 3. Выдаем Approve (разрешение) новому ClassroomDAO на снятие SGC
    APPROVE_AMOUNT = 1_000_000 * 10**18
    print(f"\nВыдача разрешения (Approve) контракту ClassroomDAO "
          f"({classroom_contract.address}) на сумму 1,000,000 SGC...")

    start_nonce = get_nonce(chairperson.address)
    token_contract.approve(classroom_contract.address, APPROVE_AMOUNT)
    wait_for_nonce(chairperson.address, start_nonce)
    print("  ✅ Approve успешно выдан!")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Батч-миграция исторического XP из students_export.csv
    #    Пропускается, если активирован режим --clean.
    # ──────────────────────────────────────────────────────────────────────────
    if args.clean:
        print("\n⏭️  Режим --clean: шаг миграции XP пропущен.")
    else:
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("📂 Батч-миграция исторического опыта (Legacy XP)")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        # Файл гарантированно существует — pre-flight check прошёл выше.
        print(f"  📄 Читаем файл: {EXPORT_CSV}")
        addresses, xp_values = load_legacy_xp(EXPORT_CSV)

        if not addresses:
            print("  ℹ️  В файле не найдено корректных записей — миграция не требуется.")
        else:
            imported = import_legacy_xp(
                classroom_contract,
                chairperson.address,
                addresses,
                xp_values,
            )

            # ── Итоговый отчёт ──────────────────────────────────────────────
            skipped = len(addresses) - imported
            print("\n┌─────────────────────────────────────────────┐")
            print("│          📊 ОТЧЁТ О МИГРАЦИИ XP             │")
            print("├─────────────────────────────────────────────┤")
            print(f"│  Всего студентов в CSV:  {len(addresses):>4}                │")
            print(f"│  ✅ Успешно импортировано: {imported:>4}              │")
            print(f"│  ❌ Пропущено (ошибки):   {skipped:>4}              │")
            print("└─────────────────────────────────────────────┘")

    # ──────────────────────────────────────────────────────────────────────────
    print("\n=============================================")
    print("🎓 Установка ClassroomDAO завершена!")
    print(f"   Новый адрес ClassroomDAO: {classroom_contract.address}")
    print("   Не забудьте обновить VOTER_ADDRESS в frontend/index.html")
    print("=============================================")


if __name__ == "__main__":
    main()
