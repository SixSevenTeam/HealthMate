import hashlib
import base64


def get_base64_md5(file_path: str) -> str:
    md5_hash = hashlib.md5()

    # Читаем файл бинарно кусками по 4 КБ
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)

    # ВАЖНО: берем .digest() (бинарный вид), а не .hexdigest() (текстовый)
    base64_encoded = base64.b64encode(md5_hash.digest()).decode('utf-8')
    return base64_encoded

    
# Подставь путь к своему PDF
file_name = "/home/hexaend/Загрузки/FULL.pdf"
result = get_base64_md5(file_name)

print(f"File: {file_name}")
print(f"MD5 Base64: {result}")