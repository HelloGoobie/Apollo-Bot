import discord
import json
from discord.ext import commands
import sqlite3
import modules.functions as functions

def hunter_role():
    with open("db/config.json") as fp:
        config = json.load(fp)
    return config["hunter_role"]

prioties = ["normal", "high"]

class Customer(commands.Cog):
    """Customer Commands"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="order")
    async def _order(self, ctx, item, amount: int, priority:str, storage = None):
        """- Place a new order"""

        with open('db/items.json') as fp:
            items = json.load(fp)

        if not items.get(item.lower()):
            await ctx.reply(embed=functions.embed_generator(self.bot, f"**{item}** is not a valid item.", 0xFF0000))
            return

        if amount < 1:
            await ctx.reply(embed=functions.embed_generator(self.bot, f"The amount must be less or equal to **{limit}**", 0xFF0000))
            return

        if priority.lower() not in prioties:
            await ctx.reply(embed=functions.embed_generator(self.bot, "The priority must be either High or Normal", 0xFF0000))
            return

        item = item.lower()
        priority = prioties.index(priority.lower())

        cost = items[item]["cost"]
        limit = items[item]["limit"]

        if amount > limit:
            await ctx.reply(embed=functions.embed_generator(self.bot, f"The amount must be less or equal to **{limit}**", 0xFF0000))
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

        if priority:
            final_cost = round(final_cost * 1.1)

        [discount_id, discount_amount] = functions.discount_active()

        discount_text = ""
        if discount_id:
            final_cost = functions.discount_price(final_cost)
            discount_text = "\n**Discount**: {}%".format(discount_amount)

        final_cost = int(round(final_cost))

        formatted_cost = "$" + format(final_cost, ",")
        name = (ctx.author.nick or ctx.author.name) + "#" + ctx.author.discriminator
        embed = discord.Embed(title="Order Placed - #{}".format(order_id), description="**Customer: **{} ({})\n**Item: **{}\n**Amount: **{}\n**Cost: **{}{}\n**Storage: **{}".format(ctx.author.mention, name, item, amount, formatted_cost, discount_text, storage))

        with open("db/config.json") as fp:
            config = json.load(fp)

        channel_id = config["orders_channel"]
        channel = await self.bot.fetch_channel(channel_id)

        if priority:
            embed.color = 0x8240AF
            message = await channel.send("A priority order has been placed", embed=embed)
        else:
            embed.color = 0xFF0000
            message = await channel.send("A new order has been placed", embed=embed)

        cur.execute(f"""INSERT INTO orders
                        (order_id, customer, product, amount, storage, cost, messageid, progress, status, priority, discount_id)
                    VALUES ({order_id}, {ctx.author.id}, ?, ?, ?, {final_cost}, {message.id}, 0,'pending', ?, ?)""", (item.lower(), amount, storage, priority, discount_id))

        con.commit()
        con.close()

        if discount_id:
            await ctx.send(embed=functions.embed_generator(self.bot, "Thank you for placing your order with Space Hunters, your order number is **#{}**\nThe cost is {} - A discount of {}% is applied".format(order_id, formatted_cost, discount_amount)))
        else:
            await ctx.send(embed=functions.embed_generator(self.bot, "Thank you for placing your order with Space Hunters, your order number is **#{}**\nThe cost is {}".format(order_id, formatted_cost)))

    @commands.command(name="orders")
    async def _orders(self, ctx,):
        con = sqlite3.connect('db/orders.db')
        cur = con.cursor()
        oginfo = f"""SELECT order_id, product, amount, cost, progress, grinder, status, priority, discount_id FROM orders WHERE customer LIKE {ctx.author.id} and status not LIKE 'cancelled' and status not LIKE 'delivered' """
        info = cur.execute(oginfo)
        userorders = info.fetchall()

        if userorders == []:
            await ctx.reply(embed=functions.embed_generator(self.bot, "Hey, you dont currently have any orders open with us! head to #Order-Here and place a new one!", colour=0xFF0000))
            return

        embed = functions.embed_generator(self.bot, "Here are your current orders:", colour=0xFFFF00, author=ctx.author.name, avatar_url=ctx.author.avatar_url)
        hasPriority = 0
        for i, x in enumerate(userorders, 1):
            grinderperson = f"<@{str(x[5])}>"
            priority = ""
            discount_text = ""

            if x[5] is None:
                grinderperson = "Not Claimed"

            if x[7]:
                hasPriority = 1
                priority = "**Priority**: High\n"

            if x[8]:
                discount_amount = functions.discount_get_amount(x[8])
                discount_text = "\n**Discount**: {}%".format(discount_amount)

            formatedPrice = "${:,}".format(x[3])
            embed.add_field(name=str(x[1]).title(), value=f"**Order ID**: {str(x[0])}\n{priority}**Product**: {str(x[1])}\n**Amount**: {str(x[2])}\n**Cost**: {formatedPrice}{discount_text}\n**Status**: {str(x[6]).title()}\n**Hunter**: {grinderperson}\n**Progress**: {str(x[4])}/{str(x[2])}", inline=True)

        if hasPriority:
            embed.colour = 0x8240AF

        await ctx.reply(embed=embed)

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

        name = ""
        priority = ""
        discount_text = ""

        if not order["grinder"]:
            name = "Unassigned"
        else:
            try:
                grinder = await self.bot.fetch_user(order["grinder"])
                name = grinder.display_name
            except commands.UserNotFound:
                name = "Unknown"

        if order["priority"]:
            priority = "**Priority**: High\n"

        if order["discount_id"]:
            discount_amount = functions.discount_get_amount(order["discount_id"])
            discount_text = "\n**Discount**: {}%".format(discount_amount)

        customer = await self.bot.fetch_user(order["customer"])
        progress = f'{order["progress"]}/{order["amount"]}' + " ({}%)".format(round((order["progress"] / order["amount"]) * 100))
        embed = functions.embed_generator(
                self.bot,
                "**Order ID: **{}\n**Customer: **{}\n{}**Product: **{}\n**Cost: **{}{}\n**Status: **{}\n**Grinder: **{}\n**Progress: **{}".format(
                    order_id,
                    customer.display_name,
                    priority,
                    order["product"],
                    "$" + format(order["cost"], ","),
                    discount_text,
                    order["status"].capitalize(),
                    name,
                    progress,
                ), colour=0x00FF00, author=customer.display_name, avatar_url=customer.avatar_url
            )

        if order["priority"]:
            embed.color = 0x8240AF

        await ctx.reply(embed=embed)



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
