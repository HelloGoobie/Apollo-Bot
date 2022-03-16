import discord
import sqlite3
import time
import json
from PIL import Image, ImageDraw, ImageFilter

img = Image.new('RGBA', (500, 500), (0, 0, 0, 0))

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
        cur.execute("UPDATE discount SET active = 0 WHERE active = 1")
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

async def blacklist_check(bot, id):
    con = sqlite3.connect('db/orders.db')
    con.row_factory = dict_factory
    cur = con.cursor()

    cur.execute("SELECT blacklist_end_date, msg FROM blacklist WHERE user_id = ? AND active = 1", (id,))
    blacklist = cur.fetchone()
    con.close()
    if not blacklist:
        return [False, 0]

    if blacklist["blacklist_end_date"] < int(time.time()):
        with open('db/config.json') as fp:
            config = json.load(fp)

        bot.guilds[0].get_member(id).remove_roles(bot.guilds[0].get_role(config["blacklist_role"]))

        con = sqlite3.connect('db/orders.db')
        con.row_factory = dict_factory
        cur = con.cursor()

        cur.execute("UPDATE blacklist SET active = 0 WHERE user_id = ? AND active = 1", (id,))
        con.commit()
        con.close()

        await bot.guilds[0].get_member(id).remove_roles(bot.guilds[0].get_role(config["blacklist_role"]))

        await bot.guilds[0].get_channel(config["blacklist_channel"]).delete_message(blacklist["msg"])

        return [False, 0]


    return [True, blacklist["blacklist_end_date"]]

def hunter_role():
    with open("db/config.json") as fp:
        config = json.load(fp)
    return config["hunter_role"]

def bxp_role():
    with open("db/config.json") as fp:
        config = json.load(fp)
    return config["bxp_role"]

def pie_chart(data):
    global img
    colours = ["#88b5e6", "#ad92df"]
    img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if sum(data) == 0:
        for i in range(len(data)):
            data[i] = 1

    #Draw pie chart
    total_amount = sum(data)
    start_angle = -90
    for i in range(len(data)):
        angle = (data[i] / total_amount) * 360
        draw.pieslice((100, 100, 500, 500), start_angle, start_angle + angle, fill=colours[i])
        start_angle += angle

    #Smooth out the edges
    img = img.filter(ImageFilter.GaussianBlur(radius=10))

    #Return image
    return img
