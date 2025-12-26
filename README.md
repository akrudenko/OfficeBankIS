# OfficeBankIS

Схема БД хранится в sql/schema.sql (генерация из SSMS, режим Schema only).

## V1.1 (Maintenance)
- Improved documentation and diagnostic notes.


### Запуск unit:
python -m unittest discover -s tests -v

#### Запуск load:
python -m tests.load_test_booking