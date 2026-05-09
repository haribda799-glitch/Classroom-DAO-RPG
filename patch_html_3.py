import re

with open("frontend/index.html", "r") as f:
    content = f.read()

# 1. Fix Margin Issue (Move Tab 4 and 5 inside content-container)
# Locate closing of content-container and move it.
pattern = r'(</p>\s*</div>\s*</div>\s*)</div>\s*(<!-- Tab 4: Store \(Market\) -->)'
replacement = r'\1\2'
content = re.sub(pattern, replacement, content, count=1)

# Now we need to append the closing div after content-marketmanager
pattern_end = r'(<div id="marketmanager-items-container" class="mt-8 space-y-4"></div>\s*</div>)'
replacement_end = r'\1\n\n    </div> <!-- End of content-container -->'
content = re.sub(pattern_end, replacement_end, content, count=1)


# 2. Add Poll Manager block in content-admin
market_logs_pattern = r'(<div id="market-logs-container"[^>]*>.*?</div>\s*</div>)'
poll_manager_html = """
            <div class="bg-slate-900/70 p-6 rounded-2xl border border-sky-500/20 shadow-[inset_0_0_15px_rgba(0,0,0,0.5)] mt-8">
                <h3 class="text-xl font-bold mb-5 text-sky-400 uppercase tracking-widest">Poll Manager</h3>
                <p class="text-sm text-slate-400 mb-4">Set dynamic topics for active quests (voting). Leave blank to use default names.</p>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <input type="text" id="poll-topic-0" placeholder="Topic 1 (e.g. Web3 Basics)" class="w-full bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-sky-500 transition-all text-sm">
                    <input type="text" id="poll-topic-1" placeholder="Topic 2 (e.g. DeFi)" class="w-full bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-sky-500 transition-all text-sm">
                    <input type="text" id="poll-topic-2" placeholder="Topic 3 (e.g. NFTs)" class="w-full bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-sky-500 transition-all text-sm">
                    <input type="text" id="poll-topic-3" placeholder="Topic 4 (e.g. DAOs)" class="w-full bg-black/50 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-sky-500 transition-all text-sm">
                </div>
                <button onclick="savePollTopics()" class="w-full py-4 mt-4 bg-slate-800 hover:bg-sky-600 hover:text-white transition-all rounded-xl font-bold border border-slate-600 hover:border-sky-400 shadow-lg text-sky-300 uppercase tracking-wider text-sm">Save Topics</button>
            </div>
"""
content = re.sub(market_logs_pattern, r'\1\n' + poll_manager_html, content, count=1, flags=re.DOTALL)


# 3. Update fetchProposals
fetch_proposals_orig = """                        const p = await voterContract.proposals(i);
                        proposalsList.push({ index: i, name: p[0], votes: p[1].toString() });"""
fetch_proposals_new = """                        const p = await voterContract.proposals(i);
                        const topics = JSON.parse(localStorage.getItem("pollTopics") || '[]');
                        const defaultTopics = ["Web3 Basics", "DeFi", "NFTs", "DAOs"];
                        let displayName = p[0];
                        if (topics[i] && topics[i].trim() !== "") {
                            displayName = topics[i].trim();
                        } else if (displayName === "" && defaultTopics[i]) {
                            displayName = defaultTopics[i];
                        } else if (topics.length === 0 && defaultTopics[i]) {
                            displayName = defaultTopics[i];
                        }
                        proposalsList.push({ index: i, name: displayName, votes: p[1].toString() });"""
content = content.replace(fetch_proposals_orig, fetch_proposals_new)


# 4. Add JS functions for Poll Manager
poll_js = """
        function loadPollTopics() {
            const topics = JSON.parse(localStorage.getItem("pollTopics") || '[]');
            for (let i = 0; i < 4; i++) {
                const el = document.getElementById(`poll-topic-${i}`);
                if (el && topics[i]) el.value = topics[i];
            }
        }

        function savePollTopics() {
            const topics = [];
            for (let i = 0; i < 4; i++) {
                const el = document.getElementById(`poll-topic-${i}`);
                topics.push(el ? el.value.trim() : "");
            }
            localStorage.setItem("pollTopics", JSON.stringify(topics));
            alert("Poll topics saved!");
            fetchProposals();
        }
"""
content = content.replace("function getMarketItems() {", poll_js + "\n        function getMarketItems() {")

# Call loadPollTopics on init or handleConnection
content = content.replace("await fetchUserData();", "await fetchUserData();\n            loadPollTopics();")

with open("frontend/index.html", "w") as f:
    f.write(content)
