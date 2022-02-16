from pydoc import describe
import re
import discord
import json
from discord.ext import commands
import sqlite3

class order(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="order")
    async def _order(self, ctx, item, amount: int, storage = None):
        with open('db/items.json') as fp:
            items = json.load(fp)
        if not items.get(item.lower()): 
            await ctx.send("Invalid Item")
            return
    
        cost = items[item.lower()]["cost"]
        limit = items[item.lower()]["limit"]

        if amount > limit: 
            await ctx.send("Exceeding limit")
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
            await ctx.send("Exceeding limit")
            con.close()
            return
        final_cost = cost * amount
        formatted_cost = "$" + format(final_cost, ",")
        embed = discord.Embed(title="Order Placed - #{}".format(order_id), description="Item: {}\nAmount: {}\nCost: {}\nStorage: {}".format(item, amount, formatted_cost, storage), colour= 0xFF0000)
        with open("db/config.json") as fp:
            config = json.load(fp)
        channel_id = config["orders_channel"]
        channel = await self.bot.fetch_channel(channel_id)

        message = await channel.send(embed=embed)

        cur.execute(f"""INSERT INTO orders 
                        (order_id, customer, amount, storage, cost, messageid, progress, status)
                    VALUES ({order_id}, {ctx.author.id}, ?, ?, {final_cost}, {message.id}, 0,'pending')""", (amount, storage))
        
        con.commit()
        con.close()

        await ctx.send("order successfully placed #{}\nThe cost is {}".format(order_id, formatted_cost))




        

        
def setup(bot):
    bot.add_cog(order(bot))
