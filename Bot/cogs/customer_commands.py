import discord
import json
from discord.ext import commands
import sqlite3
import modules.functions as functions

class Customer(commands.Cog):
    """Customer Commands"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="order")
    async def _order(self, ctx, item, amount: int, storage = None):
        """- Place a new order"""
        with open('db/items.json') as fp:
            items = json.load(fp)
        if amount < 1: 
            await ctx.reply(embed=functions.embed_generator(self.bot, "The amount must be greater than 0", 0xFF0000))
            return

        if not items.get(item.lower()): 
            await ctx.reply(embed=functions.embed_generator(self.bot, f"**{item}** is not a valid item.", 0xFF0000))
            return

        cost = items[item.lower()]["cost"]
        limit = items[item.lower()]["limit"]

        if amount > limit: 
            await ctx.reply(embed=functions.embed_generator(self.bot, "The amount must be greater than 0", 0xFF0000))
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
            await ctx.reply(embed=functions.embed_generator(self.bot, "This order, in addition to your previous orders, would exceed the limit of {} for {} orders".format(limit, item), 0xFF0000))
            con.close()
            return
        final_cost = cost * amount
        formatted_cost = "$" + format(final_cost, ",")
        name = (ctx.author.nick or ctx.author.name) + "#" + ctx.author.discriminator
        embed = discord.Embed(title="Order Placed - #{}".format(order_id), description="**Customer: **{} ({})\n**Item: **{}\n**Amount: **{}\n**Cost: **{}\n**Storage: **{}".format(ctx.author.mention, name, item, amount, formatted_cost, storage), colour= 0xFF0000)
        with open("db/config.json") as fp:
            config = json.load(fp)
        channel_id = config["orders_channel"]
        channel = await self.bot.fetch_channel(channel_id)

        message = await channel.send(f"a new order has been placed", embed=embed)

        cur.execute(f"""INSERT INTO orders 
                        (order_id, customer, product, amount, storage, cost, messageid, progress, status)
                    VALUES ({order_id}, {ctx.author.id}, ?, ?, ?, {final_cost}, {message.id}, 0,'pending')""", (item.lower(), amount, storage))

        con.commit()
        con.close()

        await ctx.send(embed=functions.embed_generator(self.bot, "Thank you for placing your order with Space Hunters, your order number is **#{}**\nThe cost is {}".format(order_id, formatted_cost)))


    @commands.command(name="track")
    async def _track(self, ctx, order_id: int):
        """- Track an order"""
        con = sqlite3.connect('db/orders.db')
        con.row_factory = functions.dict_factory
        cur = con.cursor()
        cur.execute("SELECT * FROM orders WHERE order_id LIKE ?", (order_id,))
        order = cur.fetchone()
        con.close()
        if not order:
            await ctx.reply(embed=functions.embed_generator(self.bot, "Order not found", colour=0xFF0000))
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
            embed=functions.embed_generator(
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
        

    #Errors
    @_order.error        
    async def order_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=functions.embed_generator(self.bot, "The amount must be a whole number", 0xFF0000))
            return

    @_track.error
    async def track_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=functions.embed_generator(self.bot, "The order ID must be a whole number", 0xFF0000))
            return
        

        
def setup(bot):
    bot.add_cog(Customer(bot))
