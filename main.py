#!/usr/bin/env python3
"""
TON Wallet Manager - Main Application
A modular async wallet management system for TON blockchain
"""

import asyncio
from datetime import datetime
from src.utils import generate_seeds
from src.deploy import deploy_wallet
from src.transfer import transfer_from_one_to_another, transfer_from_all_to_one
from src.balance_checker import check_wallet_balances


def display_menu():
    """Display the main menu options"""
    print("\n" + "="*50)
    print("🔵 TON Wallet Manager")
    print("="*50)
    print("1. Generate new seed phrases")
    print("2. Deploy wallets (activate)")
    print("3. Transfer from main to all wallets")
    print("4. Transfer from all wallets to main")
    print("5. Check wallet balances")
    print("0. Exit")
    print("="*50)


async def handle_option(option: str):
    """Handle the selected menu option"""
    try:
        if option == "1":
            # Ask user how to save seeds
            print("\nThis will generate new seed phrases.")
            print("How do you want to save them?")
            print("1. Overwrite existing wallets.txt")
            print("2. Create a new file (e.g., wallets_YYYYMMDD_HHMMSS.txt)")
            
            choice = ""
            while choice not in ["1", "2"]:
                choice = input("Select an option (1-2): ").strip()

            filename = "wallets.txt"
            if choice == "2":
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"wallets_{timestamp}.txt"
                print(f"Will create new file: {filename}")
            else:
                # Ask for confirmation before overwriting
                confirm = input("This will overwrite wallets.txt. Are you sure? (y/n): ").lower().strip()
                if confirm != 'y':
                    print("Operation cancelled.")
                    return True # To show menu again
                print("Will overwrite wallets.txt")

            # Get number of seeds from user
            while True:
                try:
                    num_seeds_str = input("Enter number of seeds to generate (default: 50): ").strip()
                    if not num_seeds_str:
                        num_seeds = 50
                        break
                    num_seeds = int(num_seeds_str)
                    if num_seeds > 0:
                        break
                    print("Please enter a positive number")
                except ValueError:
                    print("Please enter a valid number")

            # Generate seeds with chosen number and filename
            await generate_seeds(num_seeds, filename)
            
        elif option == "2":
            await deploy_wallet()
            
        elif option == "3":
            await transfer_from_one_to_another()
            
        elif option == "4":
            await transfer_from_all_to_one()
            
        elif option == "5":
            await check_wallet_balances()
            
        elif option == "0":
            print("👋 Goodbye!")
            return False
            
        else:
            print("❌ Invalid option! Please try again.")
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("Please try again or contact support if the issue persists")
    
    return True


async def main():
    """Main application loop"""
    print("🚀 Starting TON Wallet Manager...")
    
    try:
        while True:
            display_menu()
            
            option = input("Select an option (0-5): ").strip()
            
            # Handle the option
            should_continue = await handle_option(option)
            
            if not should_continue:
                break
                
            # Pause before showing menu again
            input("\nPress Enter to continue...")
            
    except KeyboardInterrupt:
        print("\n\n👋 Application terminated by user")
    except Exception as e:
        print(f"\n💥 Fatal error: {str(e)}")
        print("Application will exit")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main()) 