import sys
import types
import unittest
from unittest.mock import patch

# The tests exercise pure formatting/configuration code. The GitHub workflow
# installs requests before running the poster, but a local stdlib-only test run
# should not need that network client just to import the modules.
sys.modules.setdefault('requests', types.SimpleNamespace())

import fb_poster
import group_digest


class InternationalGroupDigestTest(unittest.TestCase):
    def test_all_international_markets_have_complete_configuration(self):
        self.assertEqual(10, len(group_digest.MARKET_ORDER))
        self.assertEqual(
            set(group_digest.MARKET_ORDER),
            set(group_digest.COUNTRY_CONFIGS),
        )
        self.assertEqual(
            set(group_digest.MARKET_ORDER),
            set(group_digest.MARKET_EMOJI),
        )

        for market in group_digest.MARKET_ORDER:
            config = group_digest.COUNTRY_CONFIGS[market]
            self.assertGreaterEqual(len(config['search_queries']), 6)
            self.assertTrue(config['opener_options'])
            self.assertTrue(config['soft_cta_options'])
            self.assertTrue(config['closer_options'])

    def test_digest_contains_every_market_and_group_searches(self):
        source = {'id': 'test', 'pillar': 'Tips'}
        drafts = {
            market: f'{market} draft'
            for market in group_digest.MARKET_ORDER
        }

        body = group_digest.build_issue_body(source, drafts, (None, None))

        for market in group_digest.MARKET_ORDER:
            config = group_digest.COUNTRY_CONFIGS[market]
            self.assertIn(f"{config['name']} version", body)
            self.assertIn(config['search_queries'][0], body)
            self.assertIn(
                f"Posted to one approved {config['name']} group",
                body,
            )

        self.assertLess(len(body), 60000)

    def test_page_country_bundle_weights_cover_all_markets(self):
        expected = set(group_digest.MARKET_ORDER) | {'UNIVERSAL_ONLY'}
        self.assertEqual(expected, set(fb_poster.COUNTRY_BUNDLES))
        self.assertEqual(
            100,
            sum(
                bundle['weight']
                for bundle in fb_poster.COUNTRY_BUNDLES.values()
            ),
        )

    def test_page_hashtag_mix_is_varied_unique_and_capped(self):
        self.assertGreaterEqual(len(fb_poster.TOPIC_BUNDLES), 10)

        mix = fb_poster.build_hashtag_mix(
            '#construction #contractor #jobsite #fieldmanagement #tradies',
            fb_poster.COUNTRY_BUNDLES['US']['tags'],
            fb_poster.TOPIC_BUNDLES['DAILY_REPORTING'],
            '#constructionlife #contractorlife #builders #sitework',
        )
        tags = mix.split()

        self.assertLessEqual(len(tags), fb_poster.MAX_HASHTAGS_PER_POST)
        self.assertEqual(len(tags), len({tag.lower() for tag in tags}))
        self.assertTrue(all(tag.startswith('#') for tag in tags))

    @patch('group_digest.random.choice', side_effect=lambda values: values[0])
    def test_each_market_can_generate_a_group_post(self, _mock_choice):
        post = {'content': 'Tradies keep photos and notes on site.'}

        for market in group_digest.MARKET_ORDER:
            result = group_digest.reword_for_country(post, market)
            self.assertIn('https://', result)
            self.assertGreater(len(result), len(post['content']))


if __name__ == '__main__':
    unittest.main()
