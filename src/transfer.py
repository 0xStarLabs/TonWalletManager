import asyncio
import random
from typing import List, Dict, Any
from config import DISPERSE_TON_AMOUNT
from .utils import (
    load_seeds, create_wallet_from_seed, get_wallet_balance,
    get_wallet_seqno, send_transaction_boc, create_transfer_transaction,
    await_seqno_increment
)


async def transfer_from_one_to_another() -> None:
    """Transfer TON from first wallet to all other wallets"""
    seeds = await load_seeds()
    
    if len(seeds) < 2:
        print("Need at least 2 wallets for transfers")
        return
    
    # Get main wallet (first seed)
    main_seed = seeds[0]
    main_address, main_wallet = await create_wallet_from_seed(main_seed)
    
    print(f"Main wallet address: {main_address}")
    
    # Get main wallet balance
    main_balance_info = await get_wallet_balance(main_address)
    if not main_balance_info["success"]:
        print(f"Error getting main wallet balance: {main_balance_info['error']}")
        return
    
    main_balance = main_balance_info["balance_ton"]
    print(f"Main wallet balance: {main_balance:.4f} TON")
    
    if main_balance_info["status"] != "active":
        print("Main wallet is not active! Cannot send transactions.")
        return
    
    # Get recipient wallets (all except first)
    recipient_wallets = []
    transfer_amounts = []
    
    print(f"\nGenerating random transfer amounts using range {DISPERSE_TON_AMOUNT[0]:.3f} - {DISPERSE_TON_AMOUNT[1]:.3f} TON...")
    print(f"\nRecipient wallets ({len(seeds) - 1} wallets):")
    
    for i, seed in enumerate(seeds[1:], 1):
        address, wallet = await create_wallet_from_seed(seed)
        recipient_wallets.append({"wallet": wallet, "address": address})
        
        # Generate random amount within the specified range
        amount = round(random.uniform(DISPERSE_TON_AMOUNT[0], DISPERSE_TON_AMOUNT[1]), 6)
        transfer_amounts.append(amount)
        
        print(f"Wallet #{i}: {address}")
        print(f"  → Amount to send: {amount:.6f} TON")
    
    # Calculate total needed
    total_to_send = sum(transfer_amounts)
    fee_per_transfer = 0.001
    total_fees = fee_per_transfer * len(transfer_amounts)
    total_needed = total_to_send + total_fees
    
    print(f"\n📋 Transfer Summary:")
    print("=" * 50)
    for i, (recipient, amount) in enumerate(zip(recipient_wallets, transfer_amounts), 1):
        print(f"Wallet #{i}: {amount:.6f} TON → {recipient['address'][:10]}...{recipient['address'][-6:]}")
    print("=" * 50)
    print(f"💰 Total to send: {total_to_send:.6f} TON")
    print(f"🎯 Total needed: {total_needed:.6f} TON")
    print(f"💳 Main wallet balance: {main_balance:.4f} TON")
    print("=" * 50)
    
    # Check if enough balance
    if main_balance < min(transfer_amounts) + fee_per_transfer:
        print("\n❌ Not enough balance to send even the smallest transfer!")
        return
    
    if main_balance < total_needed:
        print(f"\n⚠️  Warning: Not enough balance for all transfers!")
        print(f"You need {total_needed:.4f} TON but only have {main_balance:.4f} TON")
        
        proceed = input("Do you want to proceed anyway? (y/n): ").lower().strip()
        if proceed != 'y':
            print("Transfer cancelled.")
            return
    else:
        print(f"\n✅ Sufficient balance for all transfers!")
    
    # Confirm before proceeding
    proceed = input("Proceed with transfers? (y/n): ").lower().strip()
    if proceed != 'y':
        print("Transfer cancelled.")
        return
    
    print("\n🚀 Starting transfers...")
    
    # Perform transfers
    successful_transfers = 0
    total_sent = 0
    
    for i, (recipient, amount) in enumerate(zip(recipient_wallets, transfer_amounts)):
        try:
            print(f"\nTransfer #{i+1}:")
            print(f"  To: {recipient['address']}")
            print(f"  Amount: {amount:.4f} TON")
            
            # Check if we still have enough balance for this transfer
            current_balance_info = await get_wallet_balance(main_address)
            if current_balance_info["success"]:
                current_balance = current_balance_info["balance_ton"]
                if current_balance < amount + fee_per_transfer:
                    print(f"  ❌ Insufficient balance for this transfer (need {amount + fee_per_transfer:.6f} TON, have {current_balance:.4f} TON)")
                    continue
            
            print(f"  🔄 Sending {amount:.4f} TON...")

            max_retries = 5
            transfer_successful = False
            last_error = "Unknown error"

            for attempt in range(max_retries):
                try:
                    # Get current seqno for the main wallet. Must be fresh for each attempt.
                    seqno_result = await get_wallet_seqno(main_address)
                    if not seqno_result["success"]:
                        last_error = f"Failed to get seqno: {seqno_result.get('error', 'N/A')}"
                        await asyncio.sleep(1)
                        continue
                    
                    seqno = seqno_result["seqno"]
                    
                    boc = await create_transfer_transaction(
                        main_wallet, recipient["address"], amount, seqno
                    )
                    
                    send_result = await send_transaction_boc(boc)
                    
                    if send_result["success"]:
                        print(f"  ✅ Transfer transaction sent! Waiting for confirmation...")
                        print(f"  💳 Transaction: {send_result.get('explorer_link', 'N/A')}")
                        
                        confirmed = await await_seqno_increment(main_address, seqno)
                        if confirmed:
                            print("  🎉 Transaction confirmed on the blockchain!")
                            successful_transfers += 1
                            total_sent += amount
                            transfer_successful = True
                        else:
                            print("  ❌ Transaction was sent but confirmation timed out.")
                            last_error = "Confirmation timeout"

                        break # Exit retry loop
                    else:
                        last_error = send_result.get('error', 'Unknown send error')

                except Exception as tx_error:
                    last_error = f"Exception during transfer attempt: {str(tx_error)}"

                if attempt < max_retries - 1:
                    await asyncio.sleep(1) # Small delay between retries

            if not transfer_successful:
                print(f"  ❌ Transfer failed after {max_retries} attempts: {last_error}")
            
        except Exception as e:
            print(f"  ❌ Transfer failed: {str(e)}")
    
    print(f"\n📊 Transfer Summary:")
    print(f"Successful transfers: {successful_transfers}/{len(transfer_amounts)}")
    print(f"Total sent: {total_sent:.4f} TON")
    print(f"Estimated fees paid: {successful_transfers * fee_per_transfer:.6f} TON")
    
    if successful_transfers > 0:
        print("🎉 Transfers completed!")
    else:
        print("❌ No transfers were successful.")


async def _transfer_from_single_wallet(wallet_info: Dict[str, Any], main_address: str, amount: float) -> Dict[str, Any]:
    """Handles the transfer logic from a single wallet to the main address."""
    try:
        if amount <= 0:
            return {"success": False, "error": "Amount is zero or less", "amount": 0}
            
        print(f"\nProcessing transfer from wallet #{wallet_info['index']}:")
        print(f"  From: {wallet_info['address']}")
        print(f"  Amount: {amount:.6f} TON")
        
        print(f"  🔄 Sending {amount:.6f} TON...")

        max_retries = 5
        last_error = "Unknown error"

        for attempt in range(max_retries):
            try:
                seqno_result = await get_wallet_seqno(wallet_info["address"])
                if not seqno_result["success"]:
                    last_error = f"Failed to get seqno: {seqno_result.get('error', 'N/A')}"
                    await asyncio.sleep(1)
                    continue
                
                seqno = seqno_result["seqno"]
                
                boc = await create_transfer_transaction(
                    wallet_info["wallet"], main_address, amount, seqno
                )
                
                send_result = await send_transaction_boc(boc)
                
                if send_result["success"]:
                    print(f"  ✅ Transfer transaction sent from wallet #{wallet_info['index']}! Waiting for confirmation...")
                    print(f"  💳 Transaction: {send_result.get('explorer_link', 'N/A')}")
                    
                    confirmed = await await_seqno_increment(wallet_info["address"], seqno)
                    if confirmed:
                        print(f"  🎉 Transaction from wallet #{wallet_info['index']} confirmed!")
                        return {"success": True, "amount": amount}
                    else:
                        print(f"  ❌ Transaction from wallet #{wallet_info['index']} was sent but confirmation timed out.")
                        last_error = "Confirmation timeout"
                    
                    break
                else:
                    last_error = send_result.get('error', 'Unknown send error')
                    print(f"  Attempt {attempt + 1}/{max_retries} for wallet #{wallet_info['index']} failed: {last_error}")

            except Exception as tx_error:
                last_error = f"Exception during transfer attempt: {str(tx_error)}"
                print(f"  Attempt {attempt + 1}/{max_retries} for wallet #{wallet_info['index']} failed with exception: {last_error}")

            if attempt < max_retries - 1:
                await asyncio.sleep(1)

        print(f"  ❌ Transfer from {wallet_info['address']} failed after {max_retries} attempts: {last_error}")
        return {"success": False, "error": last_error, "amount": 0}

    except Exception as e:
        error_msg = f"Transfer failed for {wallet_info['address']}: {str(e)}"
        print(f"  ❌ {error_msg}")
        return {"success": False, "error": error_msg, "amount": 0}


async def transfer_from_all_to_one() -> None:
    """Transfer TON from all wallets to the first wallet"""
    seeds = await load_seeds()
    
    if len(seeds) < 2:
        print("Need at least 2 wallets for transfers")
        return
    
    main_seed = seeds[0]
    main_address, _ = await create_wallet_from_seed(main_seed)
    
    print(f"Target wallet address: {main_address}")
    
    main_balance_info = await get_wallet_balance(main_address)
    if main_balance_info["success"]:
        print(f"Target wallet balance: {main_balance_info['balance_ton']:.4f} TON")
    
    sender_wallets = []
    
    print(f"\nScanning sender wallets ({len(seeds) - 1} wallets):")
    
    for i, seed in enumerate(seeds[1:], 1):
        address, wallet = await create_wallet_from_seed(seed)
        
        balance_info = await get_wallet_balance(address)
        if balance_info["success"]:
            balance = balance_info["balance_ton"]
            status = balance_info["status"]
            
            if status == "active" and balance > 0.001:
                sender_wallets.append({
                    "wallet": wallet, 
                    "address": address, 
                    "balance": balance,
                    "index": i
                })
                print(f"Wallet #{i}: {address} ({balance:.6f} TON) - Will be collected.")
            else:
                print(f"Wallet #{i}: {address} - Skipped (status: {status}, balance: {balance:.6f} TON)")
    
    if not sender_wallets:
        print("\n❌ No wallets with sufficient balance found to collect from!")
        return
    
    fee_per_transfer = 0.001
    transfers_to_process = []
    total_to_collect = 0
    
    for wallet_info in sender_wallets:
        amount_to_send = max(0, wallet_info["balance"] - fee_per_transfer * 2)
        if amount_to_send > 0:
            transfers_to_process.append({"wallet_info": wallet_info, "amount": amount_to_send})
            total_to_collect += amount_to_send
            
    if not transfers_to_process:
        print("\n❌ No TON to transfer after calculating fees!")
        return

    print(f"\n📋 Collection Summary:")
    print("=" * 50)
    for transfer in transfers_to_process:
        wallet_info = transfer["wallet_info"]
        amount = transfer["amount"]
        print(f"Wallet #{wallet_info['index']}: {amount:.6f} TON from {wallet_info['address'][:10]}...{wallet_info['address'][-6:]}")
    print("=" * 50)
    print(f"💰 Total to collect: {total_to_collect:.6f} TON")
    print(f"💳 Target wallet: {main_address}")
    print("=" * 50)
    
    proceed = input("Proceed with collecting transfers? (y/n): ").lower().strip()
    if proceed != 'y':
        print("Transfer cancelled.")
        return
    
    print("\n🚀 Starting collection transfers concurrently...")
    
    tasks = [_transfer_from_single_wallet(t["wallet_info"], main_address, t["amount"]) for t in transfers_to_process]
    results = await asyncio.gather(*tasks)

    successful_transfers = sum(1 for r in results if r.get("success"))
    total_collected = sum(r.get("amount", 0) for r in results if r.get("success"))
    
    print(f"\n📊 Collection Summary:")
    print(f"Successful transfers: {successful_transfers}/{len(transfers_to_process)}")
    print(f"Total collected: {total_collected:.6f} TON")
    
    if successful_transfers > 0:
        print("🎉 Collection completed!")
    else:
        print("❌ No transfers were successful.")
