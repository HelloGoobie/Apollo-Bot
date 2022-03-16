import discord
import json
import math
import random
from discord.ext import commands
import sqlite3
import modules.functions as functions
from typing import Union
import io


def hunter_role():
    with open("db/config.json") as fp:
        config = json.load(fp)
    return config["hunter_role"]

prioties = ["normal", "high"]

maxOrder = 1

class Customer(commands.Cog):
    """Customer Commands"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="order")
    async def _order(self, ctx, item, amount: Union[int, str], priority:str, storage = None):
        """- Place a new order"""

        blacklist = await functions.blacklist_check(self.bot, id=ctx.author.id)

        if blacklist[0]:
            await ctx.reply(embed=functions.embed_generator(self.bot, f"You are blacklisted from using this bot untill <t:{blacklist[1]}:f>", colour=0xFF0000))
            return

        # check if this order would exceed the max Order
        con = sqlite3.connect("db/orders.db", timeout=10)
        cur = con.cursor()

        cur.execute("SELECT count(*) FROM orders WHERE customer LIKE {} AND status IN ('pending', 'in progress')".format(ctx.author.id))
        orders = cur.fetchone()[0]

        if orders >= maxOrder:
            await ctx.reply(embed=functions.embed_generator(self.bot, "You have reached the maximum amount of orders of {}".format(maxOrder), colour=0xFF0000))
            con.close()
            return


        with open("db/config.json") as fp:
            config = json.load(fp)

        with open('db/items.json') as fp:
            items = json.load(fp)

        if not items.get(item.lower()):
            await ctx.reply(embed=functions.embed_generator(self.bot, f"**{item}** is not a valid item.", 0xFF0000))
            return

        if amount == "max":
            amount = items[item]["limit"]
        elif amount < 1 :
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

        cur.execute("SELECT count(*) FROM orders")
        order_id = cur.fetchone()[0] + 1

        cur.execute("SELECT sum(amount) FROM orders WHERE customer LIKE {} AND status IN ('pending', 'in progress') AND product = '{}'".format(ctx.author.id, item))
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

        oType = items[item]["type"]

        formatted_cost = "$" + format(final_cost, ",")
        name = (ctx.author.nick or ctx.author.name) + "#" + ctx.author.discriminator
        embed = discord.Embed(title="{} Order Placed - #{}".format(oType, order_id), description="**Customer: **{} ({})\n**Item: **{}\n**Amount: **{}\n**Cost: **{}{}\n**Storage: **{}".format(ctx.author.mention, name, item, amount, formatted_cost, discount_text, storage))

        channel_id = config["orders_channel"]
        channel_log_id = config["orders_log_channel"]
        channel = await self.bot.fetch_channel(channel_id)
        channel_log = await self.bot.fetch_channel(channel_log_id)

        if priority:
            embed.color = 0x8240AF
            message = await channel.send("A priority order has been placed", embed=embed)
            await channel_log.send(embed=embed)
        else:
            embed.color = 0xFF0000
            message = await channel.send("A new order has been placed", embed=embed)
            await channel_log.send(embed=embed)


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
    async def _orders(self, ctx, user: Union[discord.Member, int] = None):

        if not user:
            user = ctx.author
        elif isinstance(user, int):
            user = await self.bot.fetch_user(user)

        con = sqlite3.connect('db/orders.db')
        cur = con.cursor()
        oginfo = f"""SELECT order_id, product, amount, cost, progress, grinder, status, priority, discount_id FROM orders WHERE customer LIKE {user.id} and status not LIKE 'cancelled' and status not LIKE 'delivered' """
        info = cur.execute(oginfo)
        userorders = info.fetchall()

        if userorders == []:
            await ctx.reply(embed=functions.embed_generator(self.bot, f"Hey, {user.display_name} doesn't currently have any orders open with us! head to <#942481187362975774> and place a new one!", colour=0xFF0000))
            return

        embed = functions.embed_generator(self.bot, f"{user.display_name} current orders:", colour=0xFFFF00, author=user.display_name, avatar_url=user.avatar_url)
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

    @commands.command(name="stats")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def _stats(self, ctx, user: Union[discord.Member, int] = None):
        """ - Get stats for a user"""
        con = sqlite3.connect('db/orders.db')
        con.row_factory = functions.dict_factory
        cur = con.cursor()

        if user is None:
            user = ctx.author
        elif isinstance(user, int):
            user = await self.bot.fetch_user(user)

        cur.execute("SELECT * FROM orders WHERE customer LIKE ? AND status != 'cancelled'", (user.id,))
        orders = cur.fetchall()

        cur.execute("SELECT * FROM orders WHERE grinder LIKE ? AND status != 'cancelled'", (user.id,))
        grinder_orders = cur.fetchall()

        total_orders = len(orders)
        total_spent = 0
        total_products = 0
        total_discount = 0
        total_spent_without_discount = 0

        for order in orders:
            total_products += order["amount"]
            if order["discount_id"]:
                total_discount += functions.discount_get_amount(order["discount_id"])
                total_spent += order["cost"]
                total_spent_without_discount += order["cost"] * (1 + (functions.discount_get_amount(order["discount_id"]) / 100))
            else:
                total_spent += order["cost"]
                total_spent_without_discount += order["cost"]

        total_spent = int(total_spent)
        total_spent_without_discount = int(total_spent_without_discount)

        embed = functions.embed_generator(self.bot, "Here are the stats for {}:".format(user.display_name), colour=0x00FF00, author=user.display_name, avatar_url=user.avatar_url)
        embed.add_field(name="Orders", value=total_orders, inline=True)
        embed.add_field(name="Products", value=total_products, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Spent", value="${:,}".format(total_spent), inline=True)
        embed.add_field(name="Discounts", value="{}%".format(total_discount), inline=True)
        embed.add_field(name="Spent without Discount", value="${:,}".format(total_spent_without_discount), inline=True)

        grinder = [functions.hunter_role(), functions.bxp_role()]

        if any(role.id in grinder for role in user.roles):
            total_claimed = len(grinder_orders)
            total_delivered = 0
            total_products = 0
            total_earned = 0

            for order in grinder_orders:
                total_products += order["amount"]
                if order["discount_id"]:
                    total_earned += order["cost"] * (1 + (functions.discount_get_amount(order["discount_id"]) / 100))
                else:
                    total_earned += order["cost"]
                if order["status"] == "delivered":
                    total_delivered += 1

            total_earned = int(total_earned)

            embed.add_field(name="\u200b", value="__**Grinder Stats**__", inline=False)
            embed.add_field(name="Earned", value="${:,}".format(total_earned), inline=False)
            embed.add_field(name="Claimed", value=total_claimed, inline=True)
            embed.add_field(name="Delivered", value=total_delivered, inline=True)
            embed.add_field(name="Products", value=total_products, inline=True)

            with open("db/items.json") as f:
                items = json.load(f)

            data = [0, 0]
            hunter = False
            bxp = False

            for role in user.roles:
                if role.id == grinder[0]:
                    hunter = True
                    total_claimed = 0
                    total_delivered = 0
                    total_products = 0
                    total_earned = 0

                    for order in grinder_orders:
                        if items[order["product"]]["type"] == "Cargo" or items[order["product"]]["type"] == "EXP Boost":
                            total_claimed += 1
                            total_products += order["amount"]
                            if order["discount_id"]:
                                total_earned += order["cost"] * (1 + (functions.discount_get_amount(order["discount_id"]) / 100))
                            else:
                                total_earned += order["cost"]
                            if order["status"] == "delivered":
                                total_delivered += 1

                    total_earned = int(total_earned)
                    data[0] = total_earned

                    embed.add_field(name="\u200b", value="__**Hunter Stats**__", inline=False)
                    embed.add_field(name="Earned", value="${:,}".format(total_earned), inline=False)
                    embed.add_field(name="Claimed", value=total_claimed, inline=True)
                    embed.add_field(name="Delivered", value=total_delivered, inline=True)
                    embed.add_field(name="Products", value=total_products, inline=True)

                if role.id == grinder[1]:
                    bxp = True
                    total_claimed = 0
                    total_delivered = 0
                    total_products = 0
                    total_earned = 0

                    for order in grinder_orders:
                        if items[order["product"]]["type"] == "BXP":
                            total_claimed += 1
                            total_products += order["amount"]
                            if order["discount_id"]:
                                total_earned += order["cost"] * (1 + (functions.discount_get_amount(order["discount_id"]) / 100))
                            else:
                                total_earned += order["cost"]
                            if order["status"] == "delivered":
                                total_delivered += 1

                    total_earned = int(total_earned)
                    data[1] = total_earned

                    embed.add_field(name="\u200b", value="__**BXP Stats**__", inline=False)
                    embed.add_field(name="Earned", value="${:,}".format(total_earned), inline=False)
                    embed.add_field(name="Claimed", value=total_claimed, inline=True)
                    embed.add_field(name="Delivered", value=total_delivered, inline=True)
                    embed.add_field(name="Products", value=total_products, inline=True)

        con.close()


        #if hunter and bxp:
        if False:
            img = functions.pie_chart(data)
            #Image to bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            embed.set_image(url="attachment://pie.png")
            await ctx.reply(file=discord.File(img_bytes, "pie.png"), embed=embed)

            #Delete the image from buffer
            img_bytes.close()

        else:
            await ctx.reply(embed=embed)


    @commands.command(name="slap")
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def _slap(self, ctx, user: discord.Member):

        await ctx.send(f"{ctx.author.mention} delivers an almighty backhand to the face of {user.mention}! <:plp:943133077725667388>")

    @commands.command(name="help")
    async def _help(self, ctx):

        embed = functions.embed_generator(self.bot, "Help", colour=0xFF6600)

        embed.add_field(name="__**Customer Commands:**__",
            value="**>order**: This command is used to place an order in <#942481187362975774>\n*>order [item] [amount] [priority] [storage]*\n\n" +
                "**>track**: This command allows you to track your order in <#942481187362975774>\n*>track [order number]*" +
                "\n\n**>stats**: This command allows you to see your stats\n*>stats [user]*",
            inline=False)

        embed.add_field(name="__**Hunter Commands:**__",
            value="**>claim**: This command is used to claim an order.\n*>claim [order number]*\n\n" +
                "**>progress**: This command allows you to update the progress on an order.\n*>progress [order number] [amount]*\n\n" +
                "**>delivered**: This command allows you to mark an order as delivered once the customer has received it.\n*>delivered [order number]*\n\n" +
                "**>unclaim**: This command allows a grinder to unclaim an order. Please use this only with a manager's permission.\n*>unclaim [order number]*",
            inline=False)

        embed.add_field(name="__**Admin Commands:**__",
            value="**>cancel**: This command allows an admin or manager to cancel an order with a valid reason.\n*>cancel [order number]*",
            inline=False)

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
