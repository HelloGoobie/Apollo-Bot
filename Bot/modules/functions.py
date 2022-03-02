import discord
import sqlite3
import time
import json

def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def embed_generator(bot, description, colour = 0x00FF00, author = None, avatar_url = None):
    if author is None:
        author = bot.user.name
    if avatar_url is None:
        avatar_url = bot.user.avatar_url
    embed = discord.Embed(description=description, colour=colour)
    embed.set_author(name=author, icon_url=avatar_url)
    return embed

def discount_active():
    con = sqlite3.connect('db/orders.db')
    con.row_factory = dict_factory
    cur = con.cursor()

    cur.execute("SELECT discount_id, discount_amount, discount_end_date FROM discount WHERE active = 1")
    discount = cur.fetchone()

    if discount is None:
        con.close()
        return [False, 0]

    if discount["discount_end_date"] < int(time.time()):
        cur.execute("UPDATE discounts SET active = 0 WHERE active = 1")
        con.commit()
        con.close()
        return [False, 0]

    con.close()
    return [discount["discount_id"], discount["discount_amount"]]

def discount_price(price):
    con = sqlite3.connect('db/orders.db')
    con.row_factory = dict_factory
    cur = con.cursor()

    cur.execute("SELECT discount_amount FROM discount WHERE active = 1")
    discount = cur.fetchone()
    con.close()
    if not discount:
        return price

    return int(round(price * (1 - (discount["discount_amount"] / 100))))

def discount_get_amount(id):
    con = sqlite3.connect('db/orders.db')
    con.row_factory = dict_factory
    cur = con.cursor()

    cur.execute("SELECT discount_amount FROM discount WHERE discount_id = ?", (id,))
    discount = cur.fetchone()
    con.close()
    if not discount:
        return False
    return discount["discount_amount"]

async def discount_notify_staff(bot, message):
    con = sqlite3.connect('db/orders.db')
    con.row_factory = dict_factory
    cur = con.cursor()

    cur.execute("SELECT order_id, customer, product, amount, priority, discount_id FROM orders WHERE messageid = ?", (message,))
    order = cur.fetchone()
    con.close()

    if not order:
        return

    with open("db/config.json") as fp:
        config = json.load(fp)

    with open("db/items.json") as fp:
        items = json.load(fp)

    channel_id = config["discount_channel"]
    channel = await bot.fetch_channel(channel_id)

    priority = 1.1 if order["priority"] else 1.0

    before = int(round(items[order["product"]]["cost"] * order["amount"] * priority) / 1000000)

    embed = embed_generator(bot, "New discount request\n\n**ID:** {}\n**Customer:** {}\n**Product:** {}\n**Before:** ${}".format(order['order_id'], order['customer'], order['product'], before))

    await channel.send(embed=embed)
