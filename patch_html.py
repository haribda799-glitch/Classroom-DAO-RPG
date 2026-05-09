import re
import json

with open("frontend/index.html", "r") as f:
    content = f.read()

# 1. Add Market and Market Manager tabs to tabs-container
tabs_orig = """        <button onclick="switchTab('admin')" id="tab-admin"
            class="tab-btn hidden px-8 py-3 text-lg font-semibold text-amber-500 hover:text-amber-400 transition-colors uppercase tracking-wider rounded-t-lg">
            Game Master
        </button>"""
tabs_new = tabs_orig + """
        <button onclick="switchTab('market')" id="tab-market"
            class="tab-btn px-8 py-3 text-lg font-semibold text-pink-500 hover:text-pink-400 transition-colors uppercase tracking-wider rounded-t-lg">
            Store
        </button>
        <button onclick="switchTab('marketmanager')" id="tab-marketmanager"
            class="tab-btn hidden px-8 py-3 text-lg font-semibold text-fuchsia-500 hover:text-fuchsia-400 transition-colors uppercase tracking-wider rounded-t-lg">
            Market Manager
        </button>"""
content = content.replace(tabs_orig, tabs_new)

# 2. Add content div for Market Manager and Market
content_admin_orig = """    <!-- Welcome Modal -->"""
market_divs = """
        <!-- Tab 4: Store (Market) -->
        <div id="content-market" class="tab-content glass-panel rounded-b-2xl rounded-tr-2xl p-8 border border-pink-500/30 shadow-[0_0_30px_rgba(236,72,153,0.1)]">
            <h2 class="text-3xl font-bold mb-2 text-pink-500 rpg-title">Mystic Store</h2>
            <p class="text-slate-400 mb-8 text-lg">Exchange your SGC for legendary items.</p>
            <div id="market-items-container" class="grid grid-cols-1 md:grid-cols-3 gap-5">
                <div class="text-center text-slate-500 py-8 col-span-full">Store is empty.</div>
            </div>
        </div>

        <!-- Tab 5: Market Manager -->
        <div id="content-marketmanager" class="tab-content glass-panel rounded-b-2xl rounded-tr-2xl p-8 border border-fuchsia-500/30 shadow-[0_0_30px_rgba(217,70,239,0.1)]">
            <h2 class="text-3xl font-bold mb-2 text-fuchsia-500 rpg-title">Market Manager</h2>
            <p class="text-slate-400 mb-8 text-lg">Manage assortment and prices for the Mystic Store.</p>
            <div class="bg-slate-900/70 p-6 rounded-2xl border border-fuchsia-500/20 shadow-[inset_0_0_15px_rgba(0,0,0,0.5)]">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs uppercase tracking-widest text-slate-500 mb-1 font-bold">Item Name</label>
                        <input type="text" id="market-item-name" placeholder="e.g. Health Potion" class="w-full bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-fuchsia-500 transition-all">
                    </div>
                    <div>
                        <label class="block text-xs uppercase tracking-widest text-slate-500 mb-1 font-bold">Price in SGC</label>
                        <input type="number" id="market-item-price" placeholder="e.g. 100" class="w-full bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-fuchsia-500 transition-all font-semibold">
                    </div>
                </div>
                <button onclick="addMarketItem()" class="w-full py-4 mt-4 bg-gradient-to-r from-fuchsia-600 to-pink-600 hover:from-fuchsia-500 hover:to-pink-500 transition-all rounded-xl font-bold text-white shadow-[0_0_15px_rgba(217,70,239,0.4)] hover:scale-[1.02] uppercase tracking-wider">Add Item</button>
            </div>
            <div id="marketmanager-items-container" class="mt-8 space-y-4"></div>
        </div>

"""
content = content.replace(content_admin_orig, market_divs + content_admin_orig)

# 3. Update Bestow Loot UI
bestow_orig = """                        <div>
                            <label class="block text-xs uppercase tracking-widest text-slate-500 mb-1 font-bold">Target
                                Wallet Address</label>
                            <input type="text" id="reward-address" placeholder="0x..."
                                class="w-full bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-purple-500 focus:shadow-[0_0_10px_rgba(168,85,247,0.3)] transition-all font-mono text-sm">
                        </div>

                        <div class="grid grid-cols-2 gap-4 mt-6">"""

bestow_new = """                        <div>
                            <label class="block text-xs uppercase tracking-widest text-slate-500 mb-1 font-bold">Target Wallet Address</label>
                            <input type="text" id="reward-address" placeholder="0x..." class="w-full bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-purple-500 focus:shadow-[0_0_10px_rgba(168,85,247,0.3)] transition-all font-mono text-sm">
                        </div>
                        <div class="grid grid-cols-2 gap-4 mt-4">
                            <div>
                                <label class="block text-xs uppercase tracking-widest text-slate-500 mb-1 font-bold">Target Group ID (Optional)</label>
                                <input type="number" id="reward-group" placeholder="e.g. 101" class="w-full bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-purple-500 transition-all font-semibold">
                            </div>
                            <div>
                                <label class="block text-xs uppercase tracking-widest text-slate-500 mb-1 font-bold">Custom Amount (XP)</label>
                                <input type="number" id="reward-custom-amount" placeholder="e.g. 150" class="w-full bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-purple-500 transition-all font-semibold">
                            </div>
                        </div>
                        <div class="mt-4">
                            <label class="block text-xs uppercase tracking-widest text-slate-500 mb-1 font-bold">Reason for Reward</label>
                            <input type="text" id="reward-reason" placeholder="e.g. Activity on lecture" class="w-full bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-purple-500 transition-all text-sm">
                        </div>

                        <div class="grid grid-cols-2 gap-4 mt-6">"""
content = content.replace(bestow_orig, bestow_new)

# Add custom reward and group reward buttons
buttons_orig = """                            <button onclick="rewardStudent(200)"
                                class="col-span-2 py-4 bg-gradient-to-r from-purple-700 to-indigo-700 hover:from-purple-600 hover:to-indigo-600 transition-all rounded-xl font-bold shadow-[0_0_15px_rgba(168,85,247,0.4)] flex flex-col items-center justify-center hover:scale-[1.02]">
                                <span class="text-white text-xl">+200 XP & SGC</span>
                                <span
                                    class="text-[10px] text-purple-200 uppercase tracking-widest mt-1 font-medium">Epic
                                    Boss Raid</span>
                            </button>"""
buttons_new = buttons_orig + """
                            <button onclick="rewardStudentCustom()" class="py-4 bg-slate-800 hover:bg-purple-900/50 transition-colors rounded-xl font-bold border border-slate-700 hover:border-purple-500 flex flex-col items-center justify-center group shadow-lg">
                                <span class="text-purple-400 group-hover:text-purple-300 text-lg transition-colors">Custom Reward</span>
                            </button>
                            <button onclick="rewardGroupCustom()" class="py-4 bg-gradient-to-r from-blue-700 to-cyan-700 hover:from-blue-600 hover:to-cyan-600 transition-all rounded-xl font-bold shadow-[0_0_15px_rgba(6,182,212,0.4)] flex flex-col items-center justify-center hover:scale-[1.02]">
                                <span class="text-white text-lg">Reward Group</span>
                            </button>"""
content = content.replace(buttons_orig, buttons_new)

# 4. Update ABI
with open("abi.json", "r") as f:
    abi_str = f.read().strip()
abi_match = re.search(r'const VOTER_ABI = \[.*?\];', content, re.DOTALL)
if abi_match:
    content = content.replace(abi_match.group(0), f"const VOTER_ABI = {abi_str};")

# 5. Update switchTab array
content = content.replace("['voting', 'leaderboard', 'admin']", "['voting', 'leaderboard', 'admin', 'market', 'marketmanager']")
switch_orig = """            document.getElementById('content-' + tabId).classList.add('active');

            if (tabId === 'leaderboard' && userAddress) {"""
switch_new = """            document.getElementById('content-' + tabId).classList.add('active');
            
            if (tabId === 'market' || tabId === 'marketmanager') { renderMarketItems(); }

            if (tabId === 'leaderboard' && userAddress) {"""
content = content.replace(switch_orig, switch_new)

# 6. Update handleConnection for marketmanager tab
handle_admin_orig = """            if (address.toLowerCase() === ADMIN_ADDRESS) {
                document.getElementById("tab-admin").classList.remove("hidden");
            } else {
                document.getElementById("tab-admin").classList.add("hidden");"""
handle_admin_new = """            if (address.toLowerCase() === ADMIN_ADDRESS) {
                document.getElementById("tab-admin").classList.remove("hidden");
                document.getElementById("tab-marketmanager").classList.remove("hidden");
            } else {
                document.getElementById("tab-admin").classList.add("hidden");
                document.getElementById("tab-marketmanager").classList.add("hidden");"""
content = content.replace(handle_admin_orig, handle_admin_new)

# 7. Update rewardStudent function
reward_student_orig = """        async function rewardStudent(amount) {
            const address = document.getElementById("reward-address").value.trim();
            const statusEl = document.getElementById("admin-status");
            if (!ethers.utils.isAddress(address)) {
                setStatus(statusEl, "Target a valid wallet address first.", "error");
                return;
            }

            setStatus(statusEl, `Bestowing +${amount} XP to ${address.substring(0, 6)}...`, "wait");
            try {
                const overrides = await getGasOverrides("0");
                const tx = await voterContract.rewardStudent(address, amount, overrides);"""
reward_student_new = """        async function rewardStudent(amount) {
            const address = document.getElementById("reward-address").value.trim();
            const reason = document.getElementById("reward-reason").value.trim();
            const statusEl = document.getElementById("admin-status");
            if (!ethers.utils.isAddress(address)) {
                setStatus(statusEl, "Target a valid wallet address first.", "error");
                return;
            }

            setStatus(statusEl, `Bestowing +${amount} XP to ${address.substring(0, 6)}...`, "wait");
            try {
                const overrides = await getGasOverrides("0");
                const tx = await voterContract.rewardStudent(address, amount, reason, overrides);"""
content = content.replace(reward_student_orig, reward_student_new)

# 8. Add JS for Custom Reward, Group Reward, and Market
new_js = """
        async function rewardStudentCustom() {
            const amountStr = document.getElementById("reward-custom-amount").value.trim();
            if (!amountStr) return alert("Enter custom amount");
            await rewardStudent(parseInt(amountStr));
        }

        async function rewardGroupCustom() {
            const groupIdStr = document.getElementById("reward-group").value.trim();
            const amountStr = document.getElementById("reward-custom-amount").value.trim();
            const reason = document.getElementById("reward-reason").value.trim();
            const statusEl = document.getElementById("admin-status");

            if (!groupIdStr || !amountStr) {
                setStatus(statusEl, "Need Group ID and Custom Amount.", "error");
                return;
            }

            const groupId = parseInt(groupIdStr);
            const amount = parseInt(amountStr);
            
            setStatus(statusEl, `Finding Heroes in Group ${groupId}...`, "wait");
            
            try {
                let countRes = await voterContract.get_student_count();
                let count = countRes ? countRes.toNumber() : 0;
                let targetAddresses = [];
                for (let i = 0; i < count; i++) {
                    const sAddr = await voterContract.student_addresses(i);
                    const sData = await voterContract.students(sAddr);
                    if (sData[1].toNumber() === groupId) {
                        targetAddresses.push(sAddr);
                    }
                }
                
                if (targetAddresses.length === 0) {
                    setStatus(statusEl, `No Heroes found in Group ${groupId}.`, "error");
                    return;
                }

                setStatus(statusEl, `Found ${targetAddresses.length} Heroes. Bestowing +${amount} XP...`, "wait");
                const overrides = await getGasOverrides("0");
                const tx = await voterContract.rewardBatch(targetAddresses, amount, reason, overrides);
                setStatus(statusEl, `Sending group loot... Tx: ${tx.hash.substring(0, 10)}...`, "wait");
                await tx.wait();
                setStatus(statusEl, `Group loot bestowed to ${targetAddresses.length} Heroes! 🎉`, "success");
            } catch (err) {
                console.error(err);
                setStatus(statusEl, "Group bestowal failed.", "error");
            }
        }
        
        // Market logic
        function getMarketItems() {
            const items = localStorage.getItem("classroomMarketItems");
            return items ? JSON.parse(items) : [];
        }
        
        function saveMarketItems(items) {
            localStorage.setItem("classroomMarketItems", JSON.stringify(items));
        }
        
        function addMarketItem() {
            const name = document.getElementById("market-item-name").value.trim();
            const price = document.getElementById("market-item-price").value.trim();
            if (!name || !price) return alert("Enter item name and price.");
            const items = getMarketItems();
            items.push({ id: Date.now(), name, price: parseInt(price) });
            saveMarketItems(items);
            document.getElementById("market-item-name").value = "";
            document.getElementById("market-item-price").value = "";
            renderMarketItems();
        }
        
        function removeMarketItem(id) {
            let items = getMarketItems();
            items = items.filter(i => i.id !== id);
            saveMarketItems(items);
            renderMarketItems();
        }

        function renderMarketItems() {
            const items = getMarketItems();
            
            // Render for Market Manager
            const managerContainer = document.getElementById("marketmanager-items-container");
            if (managerContainer) {
                if (items.length === 0) {
                    managerContainer.innerHTML = "<p class='text-slate-500'>No items in store.</p>";
                } else {
                    managerContainer.innerHTML = items.map(item => `
                        <div class="flex justify-between items-center bg-slate-800 p-4 rounded-xl border border-fuchsia-500/20">
                            <div>
                                <h4 class="font-bold text-white">${item.name}</h4>
                                <p class="text-fuchsia-400 font-mono text-sm">${item.price} SGC</p>
                            </div>
                            <button onclick="removeMarketItem(${item.id})" class="text-rose-500 hover:text-rose-400 font-bold text-sm uppercase">Remove</button>
                        </div>
                    `).join('');
                }
            }

            // Render for Store Tab
            const storeContainer = document.getElementById("market-items-container");
            if (storeContainer) {
                if (items.length === 0) {
                    storeContainer.innerHTML = "<div class='text-center text-slate-500 py-8 col-span-full'>Store is empty.</div>";
                } else {
                    storeContainer.innerHTML = items.map(item => `
                        <div class="bg-slate-900/60 p-6 rounded-2xl border border-pink-500/20 hover:border-pink-400 transition-all group shadow-[inset_0_0_20px_rgba(0,0,0,0.4)] flex flex-col items-center text-center">
                            <div class="w-16 h-16 rounded-full bg-gradient-to-br from-pink-600 to-rose-700 flex items-center justify-center font-bold text-2xl shadow-[0_0_15px_rgba(236,72,153,0.3)] mb-4 text-white">
                                🎁
                            </div>
                            <h3 class="font-bold text-xl text-slate-100 mb-2">${item.name}</h3>
                            <p class="text-pink-400 font-mono font-bold text-lg mb-4">${item.price} SGC</p>
                            <button onclick="alert('Purchasing not implemented in this version.')" class="w-full py-2 bg-slate-800 hover:bg-pink-600 hover:text-white transition-all rounded-xl font-bold border border-slate-600 hover:border-pink-400 shadow-lg text-pink-300 uppercase tracking-wider text-sm">
                                Buy
                            </button>
                        </div>
                    `).join('');
                }
            }
        }
"""

content = content.replace("window.addEventListener('DOMContentLoaded', init);", new_js + "\n        window.addEventListener('DOMContentLoaded', init);")

with open("frontend/index.html", "w") as f:
    f.write(content)
