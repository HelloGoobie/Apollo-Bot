import re
import discord
import json
from discord.ext import commands
import sqlite3

def hunter_role():
    with open("db/config.json") as fp:
        config = json.load(fp)
    return config["hunter_role"]


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def embed_generator(bot, description, colour = 0x00FF00):
    embed = discord.Embed(description=description, colour=colour)
    embed.set_author(name=bot.user.name, icon_url= bot.user.avatar_url)
    return embed

class order(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="order")
    async def _order(self, ctx, item, amount: int, storage = None):
        with open('db/items.json') as fp:
            items = json.load(fp)
        if amount < 1: 
            await ctx.reply(embed=embed_generator(self.bot, "The amount must be greater than 0", 0xFF0000))
            return

        if not items.get(item.lower()): 
            await ctx.reply(embed=embed_generator(self.bot, f"**{item}** is not a valid item.", 0xFF0000))
            return

        cost = items[item.lower()]["cost"]
        limit = items[item.lower()]["limit"]

        if amount > limit: 
            await ctx.reply(embed=embed_generator(self.bot, "The amount must be greater than 0", 0xFF0000))
            return

        con = sqlite3.connect("db/orders.db", timeout=10)
        cur = con.cursor()

        cur.execute("SELECT count(*) FROM orders")
        order_id = cur.fetchone()[0] + 1

        cur.execute("SELECT sum(amount) FROM orders WHERE customer LIKE {} AND status IN ('pending', 'in progress')".format(ctx.author.id))
        current_amount = cur.fetchone()[0]
        if not current_amount:
            current_amount=0

        if (current_amount + amount) > limit:
            await ctx.reply(embed=embed_generator(self.bot, "This order, in addition to your previous orders, would exceed the limit of {} for {} orders".format(limit, item), 0xFF0000))
            con.close()
            return
        final_cost = cost * amount
        formatted_cost = "$" + format(final_cost, ",")
        name = ctx.author.nick or ctx.author.name
        embed = discord.Embed(title="Order Placed - #{}".format(order_id), description="**Customer: **{} ({})\n**Item: **{}\n**Amount: **{}\n**Cost: **{}\n**Storage: **{}".format(ctx.author.mention, name, item, amount, formatted_cost, storage), colour= 0xFF0000)
        with open("db/config.json") as fp:
            config = json.load(fp)
        channel_id = config["orders_channel"]
        channel = await self.bot.fetch_channel(channel_id)

        message = await channel.send(embed=embed)

        cur.execute(f"""INSERT INTO orders
                        (order_id, customer, product, amount, storage, cost, messageid, progress, status)
                    VALUES ({order_id}, {ctx.author.id}, ?, ?, ?, {final_cost}, {message.id}, 0,'pending')""", (item.lower(), amount, storage))
      
        

        con.commit()
        con.close()

        await ctx.send(embed=embed_generator(self.bot, "Thank you for placing your order with Space Hunters, your order number is #{}\nThe cost is {}".format(order_id, formatted_cost)))


    @commands.command(name="track")
    async def _track(self, ctx, order_id: int):
        con = sqlite3.connect('db/orders.db')
        con.row_factory = dict_factory
        cur = con.cursor()
        cur.execute("SELECT * FROM orders WHERE order_id LIKE ?", (order_id,))
        order = cur.fetchone()
        con.close()
        if not order:
            await ctx.reply(embed=embed_generator(self.bot, "Order not found", colour=0xFF0000))
            return
        if not order["grinder"]:
            name = "Unassigned"
        else:
            try:
                grinder = await self.bot.fetch_user(order["grinder"])
                name = grinder.display_name
            except commands.UserNotFound:
                name = "Unknown"
        await ctx.reply(
            embed=embed_generator(
                self.bot,
                "**Order ID: **{}\n**Product: **{}\n**Cost: **{}\n**Status: **{}\n**Grinder: **{}\n**Progress: **{}".format(
                    order_id,
                    order["product"],
                    "$" + format(order["cost"], ","),
                    order["status"].capitalize(),
                    name,
                    f'{order["progress"]}/{order["amount"]}'
                    + " ({}%)".format(
                        round((order["progress"] / order["amount"]) * 100)
                    ),
                ), colour=0x00FF00
            )
        )
    
    @commands.command(name="claim")
    @commands.has_any_role(hunter_role())
    async def _claim(self, ctx, order_id: int):
        con = sqlite3.connect('db/orders.db')
        con.row_factory = dict_factory
        cur = con.cursor()

        cur.execute("SELECT * FROM orders WHERE order_id LIKE ?", (order_id,))
        order = cur.fetchone()
        if not order:
            await ctx.reply(embed=embed_generator(self.bot, "Order not found", colour=0xFF0000))
            con.close()
            return
        
        if order["status"] == "cancelled":
            await ctx.reply(embed=embed_generator(self.bot, "This order has been cancelled", colour=0xFF0000))
            con.close()
            return

        if order["grinder"]:
            await ctx.reply(embed=embed_generator(self.bot, "This order is already assigned.", colour=0xFF0000))
            con.close()
            return

        with open("db/config.json") as fp:
            config = json.load(fp)

        orders_channel = await self.bot.fetch_channel(config["orders_channel"])

        try:
            message = await orders_channel.fetch_message(order["messageid"])
            await message.delete()
        except commands.MessageNotFound:
            pass

        cur.execute("UPDATE orders SET grinder = ?, status = 'in progress' WHERE order_id LIKE ?", (ctx.author.id, order_id))
        con.commit()
        con.close()

        await ctx.reply(embed=embed_generator(self.bot, "You have successfully claimed order #{}".format(order_id)))       

        

    @commands.command(name="cancel")
    @commands.has_permissions(administrator=True)
    async def _cancel(self, ctx, order_id: int):
        con = sqlite3.connect('db/orders.db')
        con.row_factory = dict_factory
        cur = con.cursor()

        cur.execute("SELECT * FROM orders WHERE order_id LIKE ?", (order_id,))
        order = cur.fetchone()
        if not order:
            await ctx.reply(embed=embed_generator(self.bot, "Order not found", colour=0xFF0000))
            con.close()
            return
        
        if order["status"] == "cancelled":
            await ctx.reply(embed=embed_generator(self.bot, "This order is already cancelled", colour=0xFF0000))
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

        await ctx.reply(embed=embed_generator(self.bot, "You have successfully cancelled order #{}".format(order_id)))

        

    #Errors
    @_order.error        
    async def order_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=embed_generator(self.bot, "The amount must be a whole number", 0xFF0000))
            return

    @_track.error
    async def track_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=embed_generator(self.bot, "The order ID must be a whole number", 0xFF0000))
            return


    @_claim.error
    async def claim_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=embed_generator(self.bot, "The order ID must be a whole number", 0xFF0000))
            return


    @_cancel.error
    async def cancel_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=embed_generator(self.bot, "The order ID must be a whole number", 0xFF0000))
            return

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, (commands.MissingAnyRole, commands.MissingPermissions)):
            await ctx.reply(embed=embed_generator(self.bot, "You are missing the permissions required to run this command", colour=0xFF0000))
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(embed=embed_generator(self.bot, "You are missing a required argument", colour=0xFF0000))
        else:
            raise error
        

        
def setup(bot):
    bot.add_cog(order(bot))
