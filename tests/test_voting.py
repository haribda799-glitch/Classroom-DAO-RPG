import boa
import pytest

# Тестовые данные (имена предложений в формате bytes32)
NAMES = ["Alice", "Bob", "Charlie"]

@pytest.fixture
def voting():
    """Фикстура для деплоя контракта Voter.vy"""
    # Указываем точное имя файла
    return boa.load("Voter.vy", NAMES)

def test_initial_state(voting):
    """Проверяем, что контракт создался правильно"""
    # Проверяем председателя (в boa по умолчанию это boa.env.eoa)
    assert voting.chairperson() == boa.env.eoa
    
    # Проверяем, что первое предложение — это Alice
    # В Vyper 0.4.x публичные массивы возвращают структуры через индекс
    p = voting.proposals(0)
    assert p.name == NAMES[0]
    assert p.voteCount == 0

def test_give_right_to_vote(voting):
    """Проверяем выдачу прав на голосование"""
    other_user = boa.env.generate_address()
    
    # Председатель дает право голоса
    voting.give_right_to_vote(other_user)
    
    # Проверяем вес (weight) нового избирателя
    assert voting.voters(other_user).weight == 1

def test_voting_logic(voting):
    """Проверяем сам процесс голосования"""
    # Голосуем за второе предложение (индекс 1 - Bob)
    voting.vote(1)
    
    assert voting.proposals(1).voteCount == 1
    assert voting.voters(boa.env.eoa).voted is True

def test_delegation(voting):
    """Проверяем делегирование голоса"""
    chairperson = voting.chairperson()
    other_user = boa.env.generate_address()
    voting.give_right_to_vote(other_user)
    
    with boa.env.prank(other_user):
        voting.delegate(chairperson)
    
    # Теперь у председателя вес 2 (свой 1 + делегированный 1)
    assert voting.voters(chairperson).weight == 2
    
    # Голосуем и проверяем результат
    voting.vote(0)
    assert voting.proposals(0).voteCount == 2

def test_self_delegation(voting):
    """Проверяем защиту от самоделегирования"""
    with boa.reverts("Self-delegation is disallowed"):
        voting.delegate(boa.env.eoa)

def test_delegation_loop(voting):
    """Проверяем защиту от цикличности делегирования"""
    user1 = boa.env.generate_address("user1")
    user2 = boa.env.generate_address("user2")
    voting.give_right_to_vote(user1)
    voting.give_right_to_vote(user2)

    with boa.env.prank(user1):
        voting.delegate(user2)
    
    with boa.env.prank(user2):
        with boa.reverts("Found loop in delegation"):
            voting.delegate(user1)