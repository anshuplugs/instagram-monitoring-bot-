# instagram_monitor.py
import aiohttp
import random
from typing import Dict, Optional

class InstagramMonitor:
    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.session = aiohttp.ClientSession()

    def _get_random_user_agent(self) -> str:
        return random.choice([
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        ])

    async def get_profile_info(self, username: str) -> Dict:
        username = username.replace('@', '').strip().lower()
        url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        headers = {'user-agent': self._get_random_user_agent(), 'x-ig-app-id': '936619743392459'}

        try:
            async with self.session.get(url, headers=headers, proxy=self.proxy, timeout=10) as response:
                if response.status == 404:
                    return {'status': 'not_found', 'data': None}
                if response.status != 200:
                    return {'status': 'error', 'data': {'message': f'HTTP Status {response.status}'}}
                
                data = await response.json()
                if 'data' in data and (user := data['data'].get('user')):
                    return {'status': 'active', 'data': {
                        'username': user.get('username', username),
                        'full_name': user.get('full_name', 'N/A'),
                        'follower_count': user.get('edge_followed_by', {}).get('count', 0),
                        'following_count': user.get('edge_follow', {}).get('count', 0),
                        'post_count': user.get('edge_owner_to_timeline_media', {}).get('count', 0),
                        'is_private': user.get('is_private', False),
                        'is_verified': user.get('is_verified', False),
                        'bio': user.get('biography', ''),
                        'profile_pic_url': user.get('profile_pic_url_hd'),
                    }}
                else:
                    return {'status': 'private', 'data': None}
        except Exception:
            return {'status': 'error', 'data': {'message': 'Network or parsing error.'}}

    async def close(self):
        await self.session.close()
