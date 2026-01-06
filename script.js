const firebaseConfig = {
    apiKey: "AIzaSyDa1ICSJw1iYY8TRUDXuAs0dsZp64FzQgE",
    authDomain: "bol-ai-70651.firebaseapp.com",
    projectId: "bol-ai-70651",
    storageBucket: "bol-ai-70651.firebasestorage.app",
    messagingSenderId: "600504686740",
    appId: "1:600504686740:web:8e08482248bc52728f3c81"
};

firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const db = firebase.firestore(); 

let currentUser = null;
let isLoginMode = true;
let admin_custom_desc = "";
let chatContext = [];
let currentSessionId = Date.now();

// --- NEW VARIABLES FOR APPS & MEMORY ---
let registeredApps = []; // Stores apps loaded from Firestore
let userMemory = {}; // Stores user details locally

// --- LOAD USER MEMORY FROM LOCAL STORAGE ---
function loadUserMemory() {
    const savedMem = localStorage.getItem('bol_user_memory');
    if (savedMem) {
        userMemory = JSON.parse(savedMem);
        console.log("Memory Loaded:", userMemory);
    } else {
        userMemory = { name: "User", preferences: "", facts: [] };
    }
}
loadUserMemory();

// --- SAVE USER MEMORY ---
function saveUserMemoryInLocal() {
    localStorage.setItem('bol_user_memory', JSON.stringify(userMemory));
}

// --- LOAD DYNAMIC APPS FROM FIRESTORE ---
db.collection('apps').onSnapshot((snapshot) => {
    registeredApps = [];
    snapshot.forEach(doc => {
        registeredApps.push(doc.data());
    });
    console.log("Vivek System: Loaded " + registeredApps.length + " micro-apps from Cloud.");
    if(document.getElementById('activeAppCount')) {
        document.getElementById('activeAppCount').innerText = registeredApps.length;
    }
});

// --- FIRESTORE SYNC (Maintenance & Desc) ---
db.collection('settings').doc('system').onSnapshot((doc) => {
    if (doc.exists) {
        const data = doc.data();
        admin_custom_desc = data.custom_description || "";
        const maintScreen = document.getElementById('maintenance-screen');
        if (data.maintenance_mode === true) {
            maintScreen.style.display = 'flex';
        } else {
            maintScreen.style.display = 'none';
        }
    }
});

// --- AUTH LOGIC ---
auth.onAuthStateChanged(user => {
    currentUser = user;
    updateAuthUI();
    if (user) {
        db.collection('users').doc(user.uid).set({
            email: user.email,
            lastLogin: firebase.firestore.FieldValue.serverTimestamp(),
        }, { merge: true });
    }
});

function updateAuthUI() {
    const container = document.getElementById('authSection');
    if (currentUser) {
        container.innerHTML = `
            <div class="user-info">${currentUser.email} <i class="fas fa-check-circle" style="color:var(--success)"></i></div>
            <button class="auth-btn logout-btn" onclick="handleLogout()">Logout</button>
        `;
    } else {
        container.innerHTML = `<button class="auth-btn" onclick="openAuthModal('login')">Login / Sign Up</button>`;
    }
}

function openAuthModal(mode) {
    isLoginMode = (mode === 'login');
    renderAuthForm();
    document.getElementById('authModal').style.display = 'block';
    document.getElementById('overlay').style.display = 'block';
}

function toggleAuthMode() {
    isLoginMode = !isLoginMode;
    renderAuthForm();
}

function renderAuthForm() {
    const title = document.getElementById('authTitle');
    const btn = document.getElementById('authActionBtn');
    const toggle = document.getElementById('authToggleText');
    if(isLoginMode) {
        title.innerText = "Login";
        btn.innerText = "LOGIN";
        toggle.innerText = "New user? Create account";
    } else {
        title.innerText = "Sign Up";
        btn.innerText = "CREATE ACCOUNT";
        toggle.innerText = "Already have an account? Login";
    }
}

function handleAuth() {
    const email = document.getElementById('authEmail').value;
    const pass = document.getElementById('authPass').value;
    if(!email || !pass) return alert("Please fill all fields");

    if(isLoginMode) {
        auth.signInWithEmailAndPassword(email, pass).then(() => closeModals()).catch(e => alert(e.message));
    } else {
        auth.createUserWithEmailAndPassword(email, pass).then(() => {
            alert("Account created successfully!");
            closeModals();
        }).catch(e => alert(e.message));
    }
}

function handleLogout() {
    auth.signOut().then(() => window.location.reload());
}

// --- 5 MINUTE TIMER ---
setTimeout(() => {
    if (!currentUser) {
        document.getElementById('forceLoginModal').style.display = 'block';
        document.getElementById('overlay').style.display = 'block';
    }
}, 300000); 

// --- DEVELOPER MODE SECRET TRIGGER ---
let secretClicks = 0;
function handleSecretAdminClick() {
    secretClicks++;
    if (secretClicks === 5) {
        document.getElementById('adminModal').style.display = 'block';
        document.getElementById('overlay').style.display = 'block';
        secretClicks = 0;
    } else if (secretClicks === 1) {
        openModal('contactModal'); // First click opens normal contact
    }
}

// --- ADMIN: SAVE APP TO FIREBASE ---
function saveAppToFirestore() {
    const name = document.getElementById('appName').value;
    const keywords = document.getElementById('appKeywords').value.toLowerCase().split(',').map(k => k.trim());
    const code = document.getElementById('appCode').value;

    if(!name || !code) return alert("Name and Code are required.");

    db.collection('apps').add({
        name: name,
        keywords: keywords,
        code: code,
        createdAt: firebase.firestore.FieldValue.serverTimestamp()
    }).then(() => {
        alert("App Deployed to Vivek's Cloud Successfully!");
        closeModals();
        document.getElementById('appName').value = "";
        document.getElementById('appKeywords').value = "";
        document.getElementById('appCode').value = "";
    }).catch(e => alert("Error: " + e.message));
}

// --- CORE CHAT LOGIC (With Apps & Memory) ---
async function sendMessage() {
    const input = document.getElementById('userInput'), text = input.value.trim();
    if(!text) return;
    
    appendMsg('user', text);
    chatContext.push({role:'user', content:text});
    autoSaveSession(); 

    input.value = ''; input.style.height = 'auto';
    document.getElementById('thinking-box').style.display = 'flex';

    const lang = document.getElementById('langSelect').value;

    // 1. EXECUTE RELEVANT APPS (HIDDEN BACKEND LOGIC)
    let appResults = "";
    const lowerText = text.toLowerCase();
    
    registeredApps.forEach(app => {
        const isMatch = app.keywords.some(k => lowerText.includes(k));
        if (isMatch) {
            try {
                // Safe execution of app code
                const runCode = new Function(app.code);
                const result = runCode();
                appResults += `[SYSTEM APP DATA (${app.name}): ${result}] \n`;
                console.log(`Executed App: ${app.name}, Result: ${result}`);
            } catch (err) {
                console.error(`App ${app.name} Failed:`, err);
            }
        }
    });

    // 2. PREPARE SYSTEM PROMPT WITH MEMORY & APP DATA
    const memoryString = `USER PROFILE (Stored Locally): Name: ${userMemory.name}, Facts: ${JSON.stringify(userMemory.facts)}.`;
    
    const systemPrompt = `You are bol-ai, Vivek Dalvi's Reasoning Engine.
    
    ADMIN KNOWLEDGE: ${admin_custom_desc}
    REAL-TIME DATA CONTEXT: ${appResults}
    ${memoryString}

    INSTRUCTIONS:
    1. Use REAL-TIME DATA if available to answer questions like "Time", "Date", etc.
    2. If the user provides new personal info (Name, Likes, etc.), append a hidden tag at the END of your response like this:
       <<<MEMORY_UPDATE: {"name": "NewName", "fact": "User likes coding"}>>>
    3. Reply in ${lang}.
    4. Use LaTeX for math ($...$).
    `;

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                message: text, 
                system: systemPrompt, 
                history: chatContext.slice(-7) 
            })
        });

        document.getElementById('thinking-box').style.display = 'none';

        if(res.status === 429) return showError("Cloud limit reached. Vivek's clouds will reset in 60s.");
        
        const data = await res.json();
        
        if(data.choices || data.message) {
            let aiMsg = data.choices ? data.choices[0].message.content : data.message;
            
            // 3. PARSE MEMORY UPDATES
            if (aiMsg.includes("<<<MEMORY_UPDATE:")) {
                const start = aiMsg.indexOf("<<<MEMORY_UPDATE:");
                const end = aiMsg.indexOf(">>>", start);
                if (end > start) {
                    const jsonStr = aiMsg.substring(start + 17, end);
                    try {
                        const memData = JSON.parse(jsonStr);
                        if(memData.name) userMemory.name = memData.name;
                        if(memData.fact) userMemory.facts.push(memData.fact);
                        saveUserMemoryInLocal();
                        console.log("Memory Updated:", userMemory);
                    } catch(e) { console.error("Memory Parse Error", e); }
                    
                    // Remove tag from display
                    aiMsg = aiMsg.substring(0, start) + aiMsg.substring(end + 3);
                }
            }

            const tokens = Math.ceil(aiMsg.length / 4);
            // Add server info (mock or real)
            const serverInfo = data.api_index || `Vivek-Node-${Math.floor(Math.random()*5)+1}`;
            
            typeEffect(aiMsg, serverInfo, tokens);
            chatContext.push({role:'assistant', content:aiMsg});
            autoSaveSession();
        } else {
             throw new Error("No response");
        }
    } catch(e) { 
        document.getElementById('thinking-box').style.display = 'none';
        console.error(e);
        appendMsg('ai', "Connection Failed. try again after 5-10 seconds.... <br>Error: " + e.message); 
    }
}

function typeEffect(text, apiIdx, tokens) {
    const container = document.getElementById('chat-container');
    const wrap = document.createElement('div'); wrap.className = 'msg-wrapper';
    const msgDiv = document.createElement('div'); msgDiv.className = 'message ai-msg';
    wrap.appendChild(msgDiv); container.appendChild(wrap);
    
    msgDiv.innerHTML = marked.parse(text);
    
    const footer = document.createElement('div');
    footer.className = 'msg-footer';
    footer.innerHTML = `<span>Server: ${apiIdx}</span><span class="token-count">Tokens: ${tokens}</span>`;
    msgDiv.appendChild(footer);

    processAIResponse(msgDiv);
    container.scrollTop = container.scrollHeight;
}

function processAIResponse(element) {
    renderMathInElement(element, {
        delimiters: [{left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}],
        throwOnError : false
    });
    element.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
        const pre = block.parentElement;
        if (!pre.querySelector('.code-header')) {
            const header = document.createElement('div');
            header.className = 'code-header';
            header.innerHTML = `<span>Code Output</span><i class="fas fa-copy" style="cursor:pointer" onclick="copyCode(this)"></i>`;
            pre.prepend(header);
        }
    });
}

function appendMsg(role, text) {
    const container = document.getElementById('chat-container');
    const wrap = document.createElement('div'); wrap.className = 'msg-wrapper';
    wrap.innerHTML = `<div class="message ${role}-msg">${marked.parse(text)}</div>`;
    renderMathInElement(wrap, {delimiters: [{left: '$', right: '$', display: false}]});
    container.appendChild(wrap); 
    container.scrollTop = container.scrollHeight;
}

// --- AUTOMATIC SAVING LOGIC ---
function autoSaveSession() {
    if(chatContext.length === 0) return;
    let history = JSON.parse(localStorage.getItem('bol_history') || '[]');
    const existingIndex = history.findIndex(item => item.id === currentSessionId);
    let title = "New Conversation";
    const firstUserMsg = chatContext.find(m => m.role === 'user');
    if (firstUserMsg) {
        title = firstUserMsg.content.substring(0, 25) + (firstUserMsg.content.length>25 ? "..." : "");
    }
    const sessionData = { 
        id: currentSessionId, 
        title: title, 
        messages: chatContext,
        timestamp: Date.now()
    };
    if (existingIndex > -1) { history[existingIndex] = sessionData; } 
    else { history.push(sessionData); }
    localStorage.setItem('bol_history', JSON.stringify(history));
    loadHistory();
}

function manualSave() {
    if(chatContext.length === 0) return alert("System state is empty!");
    const title = prompt("Enter Session Label:");
    if(!title) return;
    const snapshotId = Date.now() + 1; 
    const history = JSON.parse(localStorage.getItem('bol_history') || '[]');
    history.push({ id: snapshotId, title, messages: chatContext });
    localStorage.setItem('bol_history', JSON.stringify(history));
    loadHistory();
}

function deleteSession(id, e) {
    e.stopPropagation();
    if(!confirm("Wipe this session?")) return;
    let history = JSON.parse(localStorage.getItem('bol_history') || '[]');
    history = history.filter(item => item.id !== id);
    localStorage.setItem('bol_history', JSON.stringify(history));
    if(id === currentSessionId) { startNewChat(); } else { loadHistory(); }
}

function loadHistory() {
    const list = document.getElementById('history-list');
    const history = JSON.parse(localStorage.getItem('bol_history') || '[]');
    list.innerHTML = "";
    history.sort((a,b) => (b.timestamp || b.id) - (a.timestamp || a.id));
    history.forEach((item) => {
        const div = document.createElement('div');
        div.className = 'history-item';
        div.innerHTML = `<span><i class="fas fa-comments"></i> ${item.title}</span><i class="fas fa-trash delete-btn" onclick="deleteSession(${item.id}, event)"></i>`;
        div.onclick = () => {
            chatContext = item.messages;
            currentSessionId = item.id;
            document.getElementById('chat-container').innerHTML = "";
            chatContext.forEach(m => appendMsg(m.role==='assistant'?'ai':'user', m.content));
            if(window.innerWidth <= 768) toggleSidebar();
        };
        list.appendChild(div);
    });
}

function changeTheme(val) { document.body.setAttribute('data-theme', val); }
function startNewChat() { 
    chatContext = []; currentSessionId = Date.now(); 
    document.getElementById('chat-container').innerHTML = ""; 
    if(window.innerWidth <= 768) toggleSidebar(); 
}
function autoExpand(el) { el.style.height = 'auto'; el.style.height = (el.scrollHeight) + 'px'; }
function toggleSidebar() { 
    const sb = document.getElementById('sidebar'), ov = document.getElementById('overlay');
    sb.classList.toggle('open');
    if(window.innerWidth <= 768) { ov.style.display = sb.classList.contains('open') ? 'block' : 'none'; }
}
function openModal(id) { document.getElementById(id).style.display='block'; document.getElementById('overlay').style.display='block'; }
function closeModals() { 
    document.querySelectorAll('.modal').forEach(e => e.style.display='none'); 
    document.getElementById('overlay').style.display='none';
    document.getElementById('sidebar').classList.remove('open');
}
function copyCode(btn) {
    const code = btn.closest('pre').querySelector('code').innerText;
    navigator.clipboard.writeText(code);
    btn.className = "fas fa-check";
    setTimeout(() => btn.className = "fas fa-copy", 1500);
}
function showError(msg) { document.getElementById('thinking-box').style.display = 'none'; appendMsg('ai', `<span style="color:var(--error); font-weight:700">${msg}</span>`); }

window.onload = loadHistory;