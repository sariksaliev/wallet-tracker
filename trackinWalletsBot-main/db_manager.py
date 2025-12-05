import sqlite3

from config import logger, DATABASE_FILE


class DatabaseManager:
    def __init__(self, db_file=DATABASE_FILE):
        try:
            self.conn = sqlite3.connect(db_file, check_same_thread=False)
            self.cursor = self.conn.cursor()
            self._create_tables()
            logger.info("Соединение с базой данных установлено.")
        except sqlite3.Error as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            raise

    def _create_tables(self):
        """Створює таблиці, якщо вони не існують."""
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS wallets
                               (
                                   user_id INTEGER,
                                   wallet_address TEXT,
                                   shortname TEXT,
                                   network TEXT, 
                                   last_tx_hash TEXT
                               )''')
        # Унікальний індекс для user_id, shortname і network
        self.cursor.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_user_shortname_network
                               ON wallets (user_id, shortname, network)''')
        self.conn.commit()

    def get_wallets(self, user_id: int):
        """Отримує всі гаманці для конкретного user_id з мережею."""
        self.cursor.execute("SELECT wallet_address, shortname, network FROM wallets WHERE user_id = ?", (user_id,))
        return self.cursor.fetchall()

    def get_wallet(self, user_id: int, address: str):
        """Отримує один гаманець з мережею."""
        self.cursor.execute("SELECT shortname, network FROM wallets WHERE user_id = ? AND wallet_address = ?", (user_id, address))
        return self.cursor.fetchone()

    def add_wallet(self, user_id: int, address: str, shortname: str, network: str) -> bool:
        """Додає новий гаманець з мережею. Повертає True при успіху, False якщо адреса або shortname вже існує."""
        if self.get_wallet(user_id, address):
            logger.info(f"Кошелек {address} уже существует для user_id {user_id}")
            return False
        self.cursor.execute("SELECT 1 FROM wallets WHERE user_id = ? AND shortname = ? AND network = ?", (user_id, shortname, network))
        if self.cursor.fetchone():
            logger.info(f"Название {shortname} ({network}) уже используется для user_id {user_id}")
            return False
        try:
            self.cursor.execute("INSERT INTO wallets (user_id, wallet_address, shortname, network, last_tx_hash) VALUES (?, ?, ?, ?, ?)",
                               (user_id, address, shortname, network, ''))
            self.conn.commit()
            logger.info(f"Добавлен кошелек {address} ({network}) из shortname {shortname} для user_id {user_id}")
            return True
        except sqlite3.IntegrityError as e:
            logger.error(f"Ошибка добавления кошелька: {e}")
            return False

    def remove_wallet(self, user_id: int, address: str, shortname: str, network: str):
        """Видаляє гаманець з мережею."""
        self.cursor.execute("DELETE FROM wallets WHERE user_id = ? AND wallet_address = ? AND shortname = ? AND network = ?",
                           (user_id, address, shortname, network))
        self.conn.commit()

    def get_all_users(self):
        """Повертає список user_id всіх користувачів."""
        try:
            self.cursor.execute("SELECT DISTINCT user_id FROM wallets")
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей: {e}")
            return []

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Соединение с базой данных закрыто.")
