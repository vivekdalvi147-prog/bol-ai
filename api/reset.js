export default async function handler(req, res) {
    const dbUrl = process.env.FIREBASE_DB_URL;
    const dbAuth = process.env.FIREBASE_AUTH_KEY;
    
    const keysRes = await fetch(`${dbUrl}/settings/api_keys.json?auth=${dbAuth}`);
    const keys = await keysRes.json();
    
    for (let i in keys) {
        await fetch(`${dbUrl}/settings/api_keys/${i}/calls.json?auth=${dbAuth}`, {
            method: "PUT", body: "0"
        });
    }
    res.status(200).send("All keys reset to 0");
}
