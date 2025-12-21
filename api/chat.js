export default async function handler(req, res) {
    if (req.method !== 'POST') return res.status(405).send('Not Allowed');
    const { message, lang, context, serverIndex } = req.body;

    const dbUrl = process.env.FIREBASE_DB_URL;
    const dbAuth = process.env.FIREBASE_AUTH_KEY;

    try {
        // 1. Minute String for Rotation
        const now = new Date();
        const minuteStr = now.toISOString().substring(0, 16).replace(/[^0-9]/g, "");

        // 2. Fetch Keys
        const keysRes = await fetch(`${dbUrl}/settings/api_keys.json?auth=${dbAuth}`);
        const keys = await keysRes.json();

        let selectedKey = null;
        let selectedIdx = null;

        // 3. Logic: Manual Select or Auto Rotation
        if (serverIndex !== 'auto' && keys[serverIndex]) {
            selectedIdx = serverIndex;
            selectedKey = keys[serverIndex].key;
        } else {
            for (let i in keys) {
                const usageRes = await fetch(`${dbUrl}/api_usage/key_${i}/${minuteStr}.json?auth=${dbAuth}`);
                const usage = await usageRes.json() || 0;
                if (usage < 5) {
                    selectedKey = keys[i].key;
                    selectedIdx = i;
                    break;
                }
            }
        }

        if (!selectedKey) return res.status(429).json({ error: "Server Busy. Try next minute." });

        // 4. OpenRouter AI Call
        const aiRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${selectedKey}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                model: "google/gemini-flash-1.5",
                messages: [
                    {role: "system", content: `You are bol.ai by Vivek Dalvi. Reply in ${lang} language.`},
                    ...context,
                    {role: "user", content: message}
                ]
            })
        });

        const data = await aiRes.json();
        
        if (!data.choices) {
            return res.status(500).json({ error: "OpenRouter Error: " + (data.error?.message || "Invalid Key") });
        }

        // 5. Increment Usage
        const usageRes = await fetch(`${dbUrl}/api_usage/key_${selectedIdx}/${minuteStr}.json?auth=${dbAuth}`);
        const currentUsage = await usageRes.json() || 0;
        await fetch(`${dbUrl}/api_usage/key_${selectedIdx}/${minuteStr}.json?auth=${dbAuth}`, {
            method: "PUT",
            body: JSON.stringify(currentUsage + 1)
        });

        res.status(200).json({ reply: data.choices[0].message.content, serverName: keys[selectedIdx].name });

    } catch (e) {
        res.status(500).json({ error: "Backend Crash: " + e.message });
    }
}
