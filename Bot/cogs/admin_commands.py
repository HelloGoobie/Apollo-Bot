import re
import discord
import json
from discord.ext import commands
import sqlite3
import modules.functions as functions
import time

def manager_role():
    with open("db/config.json") as fp:
        config = json.load(fp)
    return config["manager_role"]

class Admin(commands.Cog):
    """Admin Commands"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cancel")
    @commands.has_any_role(manager_role())
    async def _cancel(self, ctx, order_id: int):
        """- Cancel an order"""
        con = sqlite3.connect('db/orders.db')
        con.row_factory = functions.dict_factory
        cur = con.cursor()

        cur.execute("SELECT * FROM orders WHERE order_id LIKE ?", (order_id,))
        order = cur.fetchone()
        if not order:
            await ctx.reply(embed=functions.embed_generator(self.bot, "Order not found", colour=0xFF0000))
            con.close()
            return

        if order["status"] == "cancelled":
            await ctx.reply(embed=functions.embed_generator(self.bot, "This order is already cancelled", colour=0xFF0000))
            con.close()
            return

        with open("db/config.json") as fp:
            config = json.load(fp)

        orders_channel = await self.bot.fetch_channel(config["orders_channel"])

        try:
            message = await orders_channel.fetch_message(order["messageid"])
            await message.delete()
        except discord.errors.NotFound:
            pass

        cur.execute("UPDATE orders SET status = 'cancelled' WHERE order_id LIKE ?", (order_id,))
        con.commit()
        con.close()

        await ctx.reply(embed=functions.embed_generator(self.bot, "You have successfully cancelled order #{}".format(order_id)))

    @commands.command(name="newdiscount")
    @commands.has_any_role(manager_role())
    async def _newdiscount(self, ctx, discount: int, length: int):
        con = sqlite3.connect('db/orders.db')
        con.row_factory = functions.dict_factory
        cur = con.cursor()

        cur.execute("SELECT discount_end_date FROM discount WHERE active = 1")
        current_discount = cur.fetchone()
        if current_discount:
            if current_discount["discount_end_date"] < int(time.time()):
                cur.execute("UPDATE discount SET active = 0 WHERE active = 1")
                con.commit()
                con.close()
            else:
                await ctx.reply(embed=functions.embed_generator(self.bot, "There is already an active discount", colour=0xFF0000))
                con.close()
                return

        cur.execute("INSERT INTO discount (active, discount_amount, discount_start_date, discount_end_date, manager) VALUES (?, ?, ?, ?, ?)", (1, discount, int(time.time()), int(time.time()) + length * 86400, ctx.author.id))
        con.commit()
        con.close()

        manager = ctx.author.nick if ctx.author.nick else ctx.author.name

        await ctx.send(embed=functions.embed_generator(self.bot, "The discount **{}** has started for {}% off, for the next {} days has now been applied\n**Ends:** <t:{}:R>".format(manager, discount, length, int(time.time()) + length * 86400), author=manager, avatar_url=ctx.author.avatar_url))

    @commands.command(name="discount")
    @commands.has_any_role(manager_role())
    async def _discount(self, ctx):
        con = sqlite3.connect('db/orders.db')
        con.row_factory = functions.dict_factory
        cur = con.cursor()

        cur.execute("SELECT discount_amount, discount_end_date, manager FROM discount WHERE active = 1")
        discount = cur.fetchone()
        if not discount:
            await ctx.send(embed=functions.embed_generator(self.bot, "There is no active discount", colour=0xFF0000))
            con.close()
            return

        con.close()

        manager = await self.bot.fetch_user(discount["manager"])

        if not manager:
            await ctx.send(embed=functions.embed_generator(self.bot, "The manager of this discount has left the server", colour=0xFF0000))

        await ctx.send(embed=functions.embed_generator(self.bot, "The current discount is **{}%** started by **{}**\n**Ends:** <t:{}:R>".format(discount["discount_amount"], manager.name, discount["discount_end_date"]), author=manager.name, avatar_url=manager.avatar_url))

    @commands.command(name="enddiscount")
    @commands.has_any_role(manager_role())
    async def _enddiscount(self, ctx):
        con = sqlite3.connect('db/orders.db')
        con.row_factory = functions.dict_factory
        cur = con.cursor()

        cur.execute("SELECT manager, discount_amount FROM discount WHERE active = 1")
        current_discount = cur.fetchone()
        if not current_discount:
            await ctx.reply(embed=functions.embed_generator(self.bot, "There is no active discount", colour=0xFF0000))
            con.close()
            return

        cur.execute("UPDATE discount SET active = 0 WHERE active = 1")
        con.commit()
        con.close()

        manager = await self.bot.fetch_user(current_discount["manager"])

        if not manager:
            await ctx.reply(embed=functions.embed_generator(self.bot, "The manager of this discount has left the server", colour=0xFF0000))

        await ctx.reply(embed=functions.embed_generator(self.bot, "The discount of **{}%** by **{}** has now been ended".format(current_discount["discount_amount"], manager.name), 0xFF0000, author=manager.name, avatar_url=manager.avatar_url))




    #Errors
    @_cancel.error
    async def cancel_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=functions.embed_generator(self.bot, "The order ID must be a whole number", 0xFF0000))
            return


def setup(bot):
    bot.add_cog(Admin(bot))
