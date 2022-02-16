import re
import discord
import json
from discord.ext import commands
import sqlite3
import modules.functions as functions

class Admin(commands.Cog):
    """Admin Commands"""
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="cancel")
    @commands.has_permissions(administrator=True)
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
        

    #Errors
    @_cancel.error
    async def cancel_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=functions.embed_generator(self.bot, "The order ID must be a whole number", 0xFF0000))
            return        

        
def setup(bot):
    bot.add_cog(Admin(bot))
