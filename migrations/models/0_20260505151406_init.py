from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "contacts" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "external_id" VARCHAR(255) NOT NULL UNIQUE,
    "phone" VARCHAR(30),
    "email" VARCHAR(255),
    "is_active" INT NOT NULL DEFAULT 1,
    "name" VARCHAR(255),
    "gender" VARCHAR(30),
    "birth_date" VARCHAR(20),
    "avatar_url" VARCHAR(500),
    "profile_data" JSON,
    "initial_analysis" TEXT,
    "is_business" INT NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS "idx_contacts_externa_983ecb" ON "contacts" ("external_id");
CREATE INDEX IF NOT EXISTS "idx_contacts_phone_37e836" ON "contacts" ("phone");
CREATE INDEX IF NOT EXISTS "idx_contacts_email_bdebaa" ON "contacts" ("email");
CREATE TABLE IF NOT EXISTS "items" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(120) NOT NULL,
    "description" TEXT,
    "is_active" INT NOT NULL DEFAULT 1,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "messages" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "type" VARCHAR(20) NOT NULL,
    "content_text" TEXT,
    "whatsapp_status" VARCHAR(20) NOT NULL DEFAULT 'pending',
    "email_status" VARCHAR(20) NOT NULL DEFAULT 'pending',
    "email_subject" VARCHAR(255),
    "tts_audio_url" VARCHAR(500),
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "contact_id" INT NOT NULL REFERENCES "contacts" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "logs" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "action" VARCHAR(100) NOT NULL,
    "details" JSON,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "message_id" INT REFERENCES "messages" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "eJztm11zmzgUhv+Kh6vsjLcTO0nb2TvHcbbexnYncT+mnQ4jg4y1AckFkcTTyX9fSYABIY"
    "hxYmOyXCU5OgekB3H06qD81hxiQtt70yeYAoNqf7V+axg4kP0iN7VbGlgu4wZuoGBmC18j"
    "cBJGMPOoG1xsDmwPMpMJPcNFS4oIZlbs2zY3EoM5ImzFJh+jXz7UKbEgXUCXNfz4ycwIm/"
    "ABetGfy1t9jqBtpnqLTH5vYdfpailsQ0wvhSO/20w3iO07OHZeruiC4LU3wmKQFsTQBRTy"
    "y1PX593nvQtHGo0o6GnsEnQxEWPCOfBtmhjuhgwYSs6P9cYTA7T4Xf7sdk7fnb4/eXv6nr"
    "mInqwt7x6D4cVjDwIFgfFUexTtgILAQ2CMucEHCl0MbF0FsL8ArpqgFCahZAOQUUbgKmXp"
    "gAfdhtiiCw7w7KyA3Jfedf9D7/qIef3Bx0LYlA7m+jhs6gZtHG+Mc8kwwDIg1wFbIQwBrQ"
    "lGLntCeHK8AcGT41yAvCnNDzoA2aUmYhRQR347mYLI01n2RXeKaXhOiA0BzkmKyTiJ5owF"
    "bvNGZ3nGS0IEdE14K6AF/M4nkyveacfzftnCMJxKHD+PzgfXRx2BlzkhCpNZM2YqfpaYlZ"
    "H/jiZlFuLBz0o2ZhO6ZRjGEbWk+PK5cYZcutDZSl5qKqajaomyuwnKbj7KbgYluGN6yNV9"
    "t9Rak46qJcqz401YMq9cmKJNEj0umSMb8kkGsjz/uZmMc7SPFCcR/YzZUH+YyKDtlo08+v"
    "Mg+Rbg5CNPLUARxaNR75sMuH81ORcQiEctV1xFXOBcXt4xoogJb8DU98pDXhb4lInznCVe"
    "EVuTaVyAeTr4Ni3G7KzClqvJ+O/IXWafUVEz30MYegrCT+moZOQelVTZ7XYlUspwIR+2Dm"
    "iW6wVrociBarDpSImrGYa+iX7ZFeRnZmM2BnOC7VX4EhVN6+FocDPtjT6lwF/0pgPe0k3N"
    "68h69FZKK+uLtL4Opx9a/M/W98l4IGeatd/0u8b7BHxKdEzudWAmdkGRNQKTerD+0tzywa"
    "Yjmwdb6YMVnedltvltomDEDTNg3N4D19RTLYmCIct4wIKqfBlGXn68hjYQaLMPOqw3joKr"
    "HOZTfoymbmRNAiNdkkcs2+R0HdnCVmVL9Jrfm98pJDKk0NEUlVlhbxeVZVkSdpqabO1qsn"
    "utNlSRK1Nbks5G27tOwf6uk93gJXtWQiBLYY02ztPGTYVRa2Rxo54aWfx/ebBlZfEuBeEV"
    "sVR6kJsL5aBNrEYN1k4N8iVTpWIK6tTGswRM9YpwoyJ1p6BI3ckWqU1IAbIVm9P8+nQipC"
    "lNt58uTTca5lUsdVkNE1Z2lGeEclN4OujpVH4Qr8xLJPOMSsiAzFK8JC5EFv4IVwLmkHUK"
    "YEO1USpdJqss72SqZMzsgvu1NJBmCBsjGxkMNkj93k2/dzHQHqtRWBFdhcpKgM9XWslSaK"
    "O2Du0FLVJbYvQltFbkX0+l9fInK/hJYIipTuGDQgXkV97kuKb0piy93S8A9Vje0dn6QH2F"
    "ms2fqYrQ/U1abQmxyUEe7swVJ0m34CrHNVCzUP3Zv9BQ5IMnqcaBNUkIezhKSamnA99EpO"
    "z5tUxgLZnu5Ahbs3V9pVvXpvz+Kh5s2Pm0zmSbqnIliXTQViWJKh7ibmsSRvwPfs+sSST+"
    "VfDwKG5alEjPkbJFiRhr9LFl+5NQ4fecg1uOKzkE1YMuMhaaoiATtrSL6jEg9mmqMQeWmt"
    "oF1Zg76HolP34lQmpak9nFnoG/GiUghu71BLiTz4dhfarM58NEyAt8Pqxuydzp98NKj1Q8"
    "/gewSdLv"
)
