from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed = pwd_context.hash("mar6236!A@bix")
print(hashed)

print(pwd_context.verify("admin123", "$2b$12$NTrT2maCESjmsTUPixeFhOVlKJ1EGzIlObSrId6eKglhomEbIB6.G")) # → True)
