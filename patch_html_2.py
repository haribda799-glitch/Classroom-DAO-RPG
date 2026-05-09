import re
import json

with open("frontend/index.html", "r") as f:
    content = f.read()

# 1. Update ABI
with open("abi.json", "r") as f:
    abi_str = f.read().strip()
abi_match = re.search(r'const VOTER_ABI = \[.*?\];', content, re.DOTALL)
if abi_match:
    content = content.replace(abi_match.group(0), f"const VOTER_ABI = {abi_str};")

# 2. Update TOKEN_ABI
token_abi_orig = """        const TOKEN_ABI = [
            "function balanceOf(address owner) view returns (uint256)",
            "function decimals() view returns (uint8)",
            "function symbol() view returns (string)"
        ];"""
token_abi_new = """        const TOKEN_ABI = [
            "function balanceOf(address owner) view returns (uint256)",
            "function decimals() view returns (uint8)",
            "function symbol() view returns (string)",
            "function approve(address spender, uint256 amount) returns (bool)",
            "function allowance(address owner, address spender) view returns (uint256)"
        ];"""
content = content.replace(token_abi_orig, token_abi_new)

# 3. Add Beacon Timer UI to Admin
admin_status_html = """            <p id="admin-status" class="mt-6 text-center text-sm font-bold"></p>"""
beacon_timer_html = """
            <div class="bg-slate-900/70 p-6 rounded-2xl border border-rose-500/20 shadow-[inset_0_0_15px_rgba(0,0,0,0.5)] mt-8">
                <h3 class="text-xl font-bold mb-5 text-rose-400 uppercase tracking-widest flex items-center gap-2">Beacon Timer</h3>
                <div class="flex flex-col md:flex-row items-center gap-4">
                    <button onclick="generateDailyCode(event)" class="py-3 px-6 bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 transition-all rounded-xl font-bold text-white shadow-[0_0_15px_rgba(225,29,72,0.4)] whitespace-nowrap">Generate Daily Code</button>
                    <div class="text-2xl font-mono text-rose-300 font-bold tracking-widest bg-black/50 px-4 py-2 rounded-xl" id="daily-code-display">----</div>
                    <div class="text-2xl font-mono text-slate-300 font-bold bg-black/50 px-4 py-2 rounded-xl" id="daily-code-timer">05:00</div>
                </div>
            </div>

            <div class="bg-slate-900/70 p-6 rounded-2xl border border-amber-500/20 shadow-[inset_0_0_15px_rgba(0,0,0,0.5)] mt-8">
                <h3 class="text-xl font-bold mb-5 text-amber-400 uppercase tracking-widest">Market Logs</h3>
                <div id="market-logs-container" class="space-y-2 max-h-40 overflow-y-auto text-sm font-mono text-slate-400">
                    <p>Listening for purchases...</p>
                </div>
            </div>
            """
content = content.replace(admin_status_html, admin_status_html + beacon_timer_html)

# 4. Add Claim Attendance UI to Quests
quests_title_html = """            <p class="text-slate-400 mb-8 text-lg">Cast your vote to shape the realm's future.</p>"""
attendance_html = """
            <div class="bg-slate-900/50 p-6 rounded-2xl border border-sky-500/20 mb-8 flex flex-col md:flex-row items-center gap-4">
                <div class="flex-1">
                    <h3 class="text-xl font-bold text-sky-400">Claim Attendance</h3>
                    <p class="text-sm text-slate-400">Enter the Beacon Code provided by the Game Master.</p>
                </div>
                <div class="flex gap-2 w-full md:w-auto">
                    <input type="text" id="attendance-code-input" placeholder="CODE" class="w-full md:w-32 bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-sky-500 transition-all font-mono uppercase">
                    <button onclick="claimAttendance()" class="px-6 py-3 bg-sky-600 hover:bg-sky-500 transition-all rounded-xl font-bold text-white shadow-[0_0_15px_rgba(14,165,233,0.4)] whitespace-nowrap">Claim</button>
                </div>
            </div>
"""
content = content.replace(quests_title_html, quests_title_html + attendance_html)

# 5. Update renderMarketItems Buy Button
buy_btn_orig = """                            <button onclick="alert('Purchasing not implemented in this version.')" class="w-full py-2 bg-slate-800 hover:bg-pink-600 hover:text-white transition-all rounded-xl font-bold border border-slate-600 hover:border-pink-400 shadow-lg text-pink-300 uppercase tracking-wider text-sm">"""
buy_btn_new = """                            <button onclick="buyItem('${item.name}', ${item.price})" class="w-full py-2 bg-slate-800 hover:bg-pink-600 hover:text-white transition-all rounded-xl font-bold border border-slate-600 hover:border-pink-400 shadow-lg text-pink-300 uppercase tracking-wider text-sm">"""
content = content.replace(buy_btn_orig, buy_btn_new)

# 6. Add JS logic
js_to_insert = """
        let countdownInterval;
        async function generateDailyCode(event) {
            const btn = event.currentTarget;
            btn.disabled = true;
            try {
                const code = Math.random().toString(36).substring(2, 6).toUpperCase();
                // ethers.utils.id computes keccak256 of the UTF8 string
                const codeHash = ethers.utils.id(code);
                const tx = await voterContract.generateDailyCode(codeHash, await getGasOverrides("0"));
                document.getElementById("daily-code-display").innerText = "Mining...";
                await tx.wait();
                
                document.getElementById("daily-code-display").innerText = code;
                
                let timeLeft = 300;
                clearInterval(countdownInterval);
                const timerEl = document.getElementById("daily-code-timer");
                countdownInterval = setInterval(() => {
                    timeLeft--;
                    if (timeLeft < 0) {
                        clearInterval(countdownInterval);
                        timerEl.innerText = "00:00";
                        document.getElementById("daily-code-display").innerText = "----";
                        return;
                    }
                    const m = Math.floor(timeLeft / 60).toString().padStart(2, '0');
                    const s = (timeLeft % 60).toString().padStart(2, '0');
                    timerEl.innerText = `${m}:${s}`;
                }, 1000);
            } catch (err) {
                console.error(err);
                alert("Failed to generate code.");
            }
            btn.disabled = false;
        }

        async function claimAttendance() {
            const code = document.getElementById("attendance-code-input").value.trim().toUpperCase();
            if (!code) return alert("Enter code");
            try {
                const tx = await voterContract.claimAttendance(code, await getGasOverrides("0"));
                document.getElementById("voting-status").innerText = "Claiming attendance...";
                document.getElementById("voting-status").className = "mt-6 text-center text-sm font-bold text-amber-400 animate-pulse";
                await tx.wait();
                document.getElementById("voting-status").innerText = "Attendance Claimed! +50 XP 🎉";
                document.getElementById("voting-status").className = "mt-6 text-center text-sm font-bold text-emerald-400";
                document.getElementById("attendance-code-input").value = "";
                await fetchUserData();
            } catch (err) {
                console.error(err);
                if (err.message.includes("Time is up!")) alert("Time is up!");
                else if (err.message.includes("Invalid code")) alert("Invalid code!");
                else if (err.message.includes("Already claimed")) alert("Already claimed!");
                else alert("Claim failed.");
            }
        }

        async function buyItem(itemName, price) {
            try {
                const priceWei = ethers.utils.parseUnits(price.toString(), 18);
                const allowance = await tokenContract.allowance(userAddress, VOTER_ADDRESS);
                if (allowance.lt(priceWei)) {
                    alert("Approving SGC for purchase...");
                    const overrides = await getGasOverrides("0");
                    const approveTx = await tokenContract.approve(VOTER_ADDRESS, ethers.constants.MaxUint256, overrides);
                    await approveTx.wait();
                }
                
                alert(`Purchasing ${itemName} for ${price} SGC...`);
                const tx = await voterContract.buyItem(itemName, price, await getGasOverrides("0"));
                await tx.wait();
                alert(`Successfully purchased ${itemName}! 🎉`);
                await fetchUserData();
            } catch (err) {
                console.error(err);
                alert("Purchase failed. Make sure you have enough SGC.");
            }
        }
"""
content = content.replace("function getMarketItems() {", js_to_insert + "\n        function getMarketItems() {")

# 7. Add Event Listener setup in handleConnection
handle_admin_orig = """            if (address.toLowerCase() === ADMIN_ADDRESS) {
                document.getElementById("tab-admin").classList.remove("hidden");
                document.getElementById("tab-marketmanager").classList.remove("hidden");
            } else {"""
handle_admin_new = """            if (address.toLowerCase() === ADMIN_ADDRESS) {
                document.getElementById("tab-admin").classList.remove("hidden");
                document.getElementById("tab-marketmanager").classList.remove("hidden");
                
                voterContract.removeAllListeners("ItemPurchased");
                voterContract.on("ItemPurchased", async (student, itemName, price, event) => {
                    const logsContainer = document.getElementById("market-logs-container");
                    if(logsContainer.innerText.includes("Listening")) logsContainer.innerHTML = "";
                    
                    let nickname = "Unknown";
                    try {
                        const sData = await voterContract.students(student);
                        nickname = sData[0] || "Unknown";
                    } catch(e) {}
                    
                    const time = new Date().toLocaleTimeString();
                    const logEntry = document.createElement("p");
                    logEntry.innerHTML = `<span class="text-slate-500">[${time}]</span> <span class="text-emerald-400">Purchase Successful:</span> <b>${nickname}</b> bought <b>${itemName}</b> for ${price} SGC`;
                    logsContainer.prepend(logEntry);
                });
                
            } else {"""
content = content.replace(handle_admin_orig, handle_admin_new)

with open("frontend/index.html", "w") as f:
    f.write(content)
