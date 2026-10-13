from app.models import User

def test_user_password_hashing():
    u = User(username='testuser', email='test@test.com')
    u.set_password('MySecretPassword123')
    assert u.password_hash != 'MySecretPassword123'
    assert u.check_password('MySecretPassword123') is True
    assert u.check_password('WrongPassword') is False

def test_user_registration(client):
    res = client.post('/auth/register', data={
        'username': 'Charlie Brown',
        'email': 'charlie@example.com',
        'currency': '$',
        'password': 'StrongPassword123!',
        'confirm_password': 'StrongPassword123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    user = User.query.filter_by(email='charlie@example.com').first()
    assert user is not None
    assert user.username == 'Charlie Brown'

def test_registration_duplicate_email(client, user_a):
    res = client.post('/auth/register', data={
        'username': 'Alice Clone',
        'email': 'alice@example.com',
        'currency': '$',
        'password': 'AnotherPassword123!',
        'confirm_password': 'AnotherPassword123!'
    })
    assert res.status_code == 200
    assert b'An account with this email address already exists' in res.data

def test_registration_password_mismatch(client):
    res = client.post('/auth/register', data={
        'username': 'David',
        'email': 'david@example.com',
        'currency': '$',
        'password': 'Password123!',
        'confirm_password': 'DifferentPassword456!'
    })
    assert res.status_code == 200
    assert b'Passwords must match' in res.data
    assert User.query.filter_by(email='david@example.com').first() is None

def test_login_success_and_logout(client, user_a):
    res = client.post('/auth/login', data={
        'email': 'alice@example.com',
        'password': 'Password123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Welcome back, Alice User' in res.data

    logout_res = client.get('/auth/logout', follow_redirects=True)
    assert logout_res.status_code == 200
    assert b'You have been safely signed out' in logout_res.data

def test_login_invalid_password(client, user_a):
    res = client.post('/auth/login', data={
        'email': 'alice@example.com',
        'password': 'IncorrectPassword'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Invalid email or password' in res.data
