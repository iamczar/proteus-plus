import unittest
import aiohttp
import asyncio

OWNER = "iamczar"
REPO = "proteus-plus"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"


async def fetch_releases():
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL) as response:
            if response.status == 200:
                latest = await response.json()
                return latest["tag_name"]
            return None  # Return None on failure


class GithubTestIntegration(unittest.TestCase):

    def test_fetch_latest_release(self):
        # Run the async function within the event loop
        latest = asyncio.run(fetch_releases())

        self.assertIsNotNone(latest)
        self.assertIsInstance(latest, str)

        print("\nAvailable Releases:", latest)


if __name__ == "__main__":
    unittest.main()
