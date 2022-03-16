import discord
from discord.ext import commands
import modules.functions as functions

class errors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            pass
        elif isinstance(error, (commands.MissingAnyRole, commands.MissingPermissions)):
            await ctx.reply(embed=functions.embed_generator(self.bot, "You are missing the permissions required to run this command, please check the #information page or contact a member of staff", colour=0xFF0000))

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(embed=functions.embed_generator(self.bot, "Something doesn't look quite right, if you're not sure how to place an order please check out #how-to-order! ", colour=0xFF0000))
            
        else:
            raise error
        
def setup(bot):
    bot.add_cog(errors(bot))
