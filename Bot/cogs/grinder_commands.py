import re
import discord
import json
from discord.ext import commands
import sqlite3
import modules.functions as functions
from typing import Union

def hunter_role():
    with open("db/config.json") as fp:
        config = json.load(fp)
    return config["hunter_role"]

def bxp_role():
    with open("db/config.json") as fp:
        config = json.load(fp)
    return config["bxp_role"]

class Grinder(commands.Cog):
    """Grinder Commands"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="claim")
    @commands.has_any_role(functions.hunter_role(), functions.bxp_role())
    async def _claim(self, ctx, order_id: int):
        """- Claim an order"""
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
            await ctx.reply(embed=functions.embed_generator(self.bot, "This order has been cancelled", colour=0xFF0000))
            con.close()
            return

        if order["grinder"]:
            await ctx.reply(embed=functions.embed_generator(self.bot, "This order is already assigned.", colour=0xFF0000))
            con.close()
            return

        with open("db/config.json") as fp:
            config = json.load(fp)

        cur.execute("UPDATE orders SET grinder = ?, status = 'in progress' WHERE order_id LIKE ?", (ctx.author.id, order_id))
        con.commit()
        con.close()

        await ctx.reply(embed=functions.embed_generator(self.bot, "You have successfully claimed order #{}".format(order_id)))

        # delete order messageid
        await self.bot.http.delete_message(config["orders_channel"], order["messageid"])


    @commands.command(name="progress")
    @commands.has_any_role(functions.hunter_role(), functions.bxp_role())
    async def _progress(self, ctx, order_id: int, progress: str):
        """- Update an order"""

        # Progress must be integer or start with + or - and integer
        if not re.match(r"^[+-]?\d+$", progress):
            await ctx.reply(embed=functions.embed_generator(self.bot, "Progress must be an integer", colour=0xFF0000))
            return


        con = sqlite3.connect('db/orders.db')
        con.row_factory = functions.dict_factory
        cur = con.cursor()
        cur.execute("SELECT * FROM orders WHERE order_id LIKE ?", (order_id,))
        order = cur.fetchone()

        # Check if order exists, author is grinder, order is in progress, progress is not over order amount, progress is not negative

        if not order:
            await ctx.reply(embed=functions.embed_generator(self.bot, "Order not found", colour=0xFF0000))
            con.close()
            return

        if ctx.author.id != order["grinder"]:
            await ctx.reply(embed=functions.embed_generator(self.bot, "This order is not assigned to you", 0xFF0000))
            con.close()
            return

        if order["status"] != "in progress":
            await ctx.reply(embed=functions.embed_generator(self.bot, "The order status is `{}`. The order must be `in progress` to make changes.".format(order["status"]), 0xFF0000))
            con.close()
            return


        if not isinstance(progress, int) and (progress.startswith("+") or progress.startswith("-")):
            operator = progress[0]
            progress = int(progress[1:])
            progress = order["progress"] + progress if operator == "+" else order["progress"] - progress
        else:
            progress = int(progress)


        if progress > order["amount"]:
            await ctx.reply(embed=functions.embed_generator(self.bot, "{} is exceeding the amount required".format(progress), 0xFF0000))
            con.close()
            return

        if progress < 0:
            await ctx.reply(embed=functions.embed_generator(self.bot, "Progress cannot be negative", 0xFF0000))
            con.close()
            return

        # Update progress, if

        if progress == order["amount"]:
            with open('db/config.json') as fp:
                config = json.load(fp)
            collection_channel = await self.bot.fetch_channel(config["collection_channel"])
            try:
                grinder = await self.bot.fetch_user(order["grinder"])
                name = f"{grinder.mention} ({grinder.display_name}#{grinder.discriminator})"
            except:
                name = "Please contact staff"
            await collection_channel.send(f"<@{order['customer']}>", embed=functions.embed_generator(self.bot, "**Order #{} - Ready For Collection**\n**Product: **{}\n**Amount: **{}\n**Cost: **{}\n**Grinder: **{}".format(
                order_id,
                order["product"],
                order["amount"],
                "$" + format(order["cost"], ","),
                name
            ), 0x00FF00))
            cur.execute("UPDATE orders SET progress = amount, status = 'complete' WHERE order_id LIKE ?", (order_id,))
            con.commit()
            con.close()
            await ctx.reply(embed=functions.embed_generator(self.bot, "Successfully updated order #{}.\nThe customer has been notified that their order is complete.".format(order_id), 0x00FF00))

        else:
            cur.execute("UPDATE orders SET progress = ? WHERE order_id LIKE ?", (progress, order_id))
            con.commit()
            con.close()
            await ctx.reply(embed=functions.embed_generator(self.bot, "Successfully updated order #{}.\n**Progress: ** {}/{} ({}%)".format(
                order_id,
                progress,
                order["amount"],
                round((progress/order["amount"]) * 100)
            ), colour=0x00FF00))

    @commands.command(name="current")
    async def _current(self, ctx, user: Union[discord.Member, int] = None):

        if user is None:
            user = ctx.author
        elif isinstance(user, int):
            user = await self.bot.fetch_user(user)

        con = sqlite3.connect('db/orders.db')
        cur = con.cursor()
        oginfo = f"""SELECT order_id, customer, product, amount , cost , progress , grinder, status FROM orders WHERE grinder LIKE {user.id} and status not LIKE 'cancelled' and status not LIKE 'delivered' """
        info = cur.execute(oginfo)
        userorders = info.fetchall()

        if userorders == []:
            await ctx.reply(embed=functions.embed_generator(self.bot, f"Hey, {user.display_name} doesn't currently have any orders assigned!", colour=0xFF0000))
            return

        embed = discord.Embed(title=f"{ctx.author}'s Orders! ", colour = 0x00FF00)
        for i, x in enumerate(userorders, 1):
            grinderperson = f"<@{str(x[6])}>"
            if grinderperson is None:
                grinderperson = "Not Claimed"

            formatedPrice = "${:,}".format(x[4])
            embed.add_field(name=f"Order #{str(x[0])}", value=f"**Customer**: <@{str(x[1])}>\n**Product**: {str(x[2]).title()}\n**Amount**: {str(x[3])}\n**Cost**: {formatedPrice}\n**Status**: {str(x[7]).title()}\n**Hunter**: {grinderperson}\n**Progress**: {str(x[5])}/{str(x[3])}", inline=True)
        await ctx.reply(embed=embed)


    @commands.command(name="delivered")
    @commands.has_any_role(functions.hunter_role(), functions.bxp_role())
    async def _delivered(self, ctx, order_id: int):
        """- Deliver an order"""
        con = sqlite3.connect('db/orders.db')
        con.row_factory = functions.dict_factory
        cur = con.cursor()
        cur.execute("SELECT * FROM orders WHERE order_id LIKE ?", (order_id,))
        order = cur.fetchone()

        if not order:
            await ctx.reply(embed=functions.embed_generator(self.bot, "Order not found", colour=0xFF0000))
            con.close()
            return

        if order["grinder"] != ctx.author.id:
            await ctx.reply(embed=functions.embed_generator(self.bot, "This order is not assigned to you", 0xFF0000))
            con.close()
            return

        if order["status"] != "complete":
            await ctx.reply(embed=functions.embed_generator(self.bot, "The order status is `{}`. The order must be `complete` to mark as delivered.".format(order["status"]), 0xFF0000))

            con.close()
            return

        cur.execute("UPDATE orders SET status = 'delivered' WHERE order_id like ?", (order_id,))
        con.commit()
        con.close()
        await ctx.reply(embed=functions.embed_generator(self.bot, "Successfully delivered order #{}".format(order_id), 0x00FF00))

    @commands.command(name="unclaim")
    @commands.has_any_role(functions.hunter_role(), functions.bxp_role())
    async def _unclaim(self, ctx, order_id:int):
        """- Unclaim an order"""
        con = sqlite3.connect('db/orders.db')
        con.row_factory = functions.dict_factory
        cur = con.cursor()

        cur.execute("UPDATE orders SET grinder = NULL, status = 'pending' WHERE order_id LIKE ?", (order_id,))
        con.commit()
        con.close()

        await ctx.reply(embed=functions.embed_generator(self.bot, "You have unclaimed order #{}, if you haven't already please inform a member of the management team as to why you can no longer do this order, or if it was a mistake simply >claim the order again".format(order_id)))
    #Errors
    @_claim.error
    async def claim_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=functions.embed_generator(self.bot, "The order ID must be a whole number", 0xFF0000))
            return

    @_progress.error
    async def progress_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=functions.embed_generator(self.bot, "The order ID must be a whole number", 0xFF0000))
            return

    @_delivered.error
    async def delivered_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=functions.embed_generator(self.bot, "The order ID must be a whole number", 0xFF0000))
            return


def setup(bot):
    bot.add_cog(Grinder(bot))
