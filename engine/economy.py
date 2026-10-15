"""
Economy system — shops, currency, item pricing.
"""
import random
from .config import Config
cfg = Config()

class Economy:
    def __init__(self, world):
        self.world = world
        self.shops = {}  # vnum -> Shop
        self.market_prices = {}  # item_vnum -> current_price (for dynamic pricing)
    
    def register_shop(self, shop):
        self.shops[shop.vnum] = shop
    
    def get_shop(self, vnum):
        return self.shops.get(vnum)
    
    def get_shop_at_room(self, room_vnum):
        for shop in self.shops.values():
            if shop.room_vnum == room_vnum:
                return shop
        return None
    
    def buy_price(self, shop, item):
        """Calculate how much a shop sells an item for."""
        base = item.value
        return int(base * shop.markup * cfg.SHOP_MARKUP)
    
    def sell_price(self, shop, item):
        """Calculate how much a shop will pay for an item."""
        base = item.value
        if base <= 0:
            return 0
        # Check if shop buys this type
        if item.item_type not in shop.buy_types:
            return 0
        # Check no_sell flags
        for flag in item.flags:
            if flag in shop.no_sell_flags:
                return 0
        price = int(base * shop.demarkup * cfg.SHOP_DEMARKUP)
        return max(1, min(price, shop.profit_cap))
    
    def buy_item(self, shop, player, item_vnum):
        """Player buys an item from a shop. Returns item or None."""
        if item_vnum not in shop.products:
            player.send("That item is not sold here.")
            return None
        
        # Find the item in shop inventory
        item_template = self.world.item_templates.get(item_vnum)
        if not item_template:
            player.send("That item is not available.")
            return None
        
        price = self.buy_price(shop, item_template)
        if player.gold < price:
            player.send(f"That costs {price} gold, which you don't have.")
            return None
        
        player.gold -= price
        from .entity import ItemInstance
        item = ItemInstance(item_template)
        player.inventory.append(item)
        player.send(f"You buy {item.short_desc} for {price} gold.")
        return item
    
    def sell_item(self, shop, player, item):
        """Player sells an item to a shop."""
        # Remove from inventory
        if item not in player.inventory:
            # Check equipment
            for slot, eq in list(player.equipment.slots.items()):
                if eq is item:
                    player.equipment.unequip(slot)
                    break
            else:
                player.send("You don't have that item.")
                return False
        
        if item in player.inventory:
            player.inventory.remove(item)
        
        price = self.sell_price(shop, item)
        if price <= 0:
            player.send(f"The shopkeeper has no interest in {item.short_desc}.")
            # Give item back
            player.inventory.append(item)
            return False
        
        player.gold += price
        player.send(f"You sell {item.short_desc} for {price} gold.")
        
        # Dynamic pricing: sell to shop decreases future buy price
        if item.template and item.template.vnum in self.market_prices:
            self.market_prices[item.template.vnum] = max(1, 
                int(self.market_prices[item.template.vnum] * 0.95))
        
        return True
    
    def list_shop_items(self, shop, player):
        """Show shop's inventory to player."""
        if not shop.products:
            player.send("The shop is currently empty.")
            return
        
        player.send(f"\x1b[33m{shop.name}\x1b[0m")
        player.send(f"{'Item':<40} {'Price':>10}")
        player.send("-" * 52)
        
        for item_vnum in shop.products:
            template = self.world.item_templates.get(item_vnum)
            if template:
                price = self.buy_price(shop, template)
                player.send(f"{template.short_desc:<40} {price:>10} gold")
        
        player.send(f"\nYour gold: {player.gold}")
