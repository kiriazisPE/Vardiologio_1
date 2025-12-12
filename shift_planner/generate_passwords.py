"""
Generate new bcrypt password hashes for authentication
Run this script to create new secure passwords
"""

import bcrypt
import secrets
import string

def generate_password(length=16):
    """Generate a strong random password"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

if __name__ == '__main__':
    print("=" * 60)
    print("SECURE PASSWORD GENERATOR")
    print("=" * 60)
    print("\nGenerating new passwords and hashes...\n")
    
    users = ['admin', 'manager', 'user']
    credentials = {}
    
    for user in users:
        password = generate_password(20)  # 20-character strong password
        hashed = hash_password(password)
        credentials[user] = {'password': password, 'hash': hashed}
        
        print(f"User: {user}")
        print(f"Password: {password}")
        print(f"Hash: {hashed}")
        print("-" * 60)
    
    print("\n" + "=" * 60)
    print("YAML CONFIGURATION")
    print("=" * 60)
    print("\nCopy this to your .streamlit/auth.yaml file:\n")
    
    print("credentials:")
    print("  usernames:")
    for user in users:
        email = f"{user}@shiftplanner.com"
        name = user.capitalize() if user != 'admin' else 'Administrator'
        
        print(f"    {user}:")
        print(f"      email: {email}")
        print(f"      name: {name}")
        print(f"      password: {credentials[user]['hash']}")
    
    print("\n" + "=" * 60)
    print("⚠️  IMPORTANT:")
    print("=" * 60)
    print("1. Save the passwords in a secure password manager")
    print("2. Update .streamlit/auth.yaml with the hashes")
    print("3. NEVER commit auth.yaml to git")
    print("4. Share passwords securely with users")
    print("=" * 60)
