import fetch from 'node-fetch';

async function test(message) {
  console.log(`\nTesting: "${message}"`)
  try {
    const res = await fetch('http://localhost:8000/api/chatbot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        guestId: 'test-guest-789'
      })
    });
    const data = await res.json();
    console.log(data.messages?.[0]?.text || data);
  } catch (err) {
    console.error(err);
  }
}

await test("Giá iPhone 17 Pro");
await test("Cho tôi biết giá Samsung Galaxy Z Fold7");
