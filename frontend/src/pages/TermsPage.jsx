import { Link } from 'react-router-dom'
import { canonicalFor } from '../seo'

export default function TermsPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <title>Terms of Use — BikeGrid</title>
      <meta name="description" content="Read the BikeGrid terms of use, including our data accuracy disclaimer, affiliate disclosure, and liability policy." />
      <link rel="canonical" href={canonicalFor('/terms')} />
      <h1 className="text-2xl font-semibold text-slate-900 mb-2">Terms of Use</h1>
      <p className="text-sm text-slate-400 mb-8">Last updated: May 2026</p>

      <div className="space-y-8 text-slate-600 leading-relaxed text-sm">
        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">1. Acceptance of terms</h2>
          <p>
            By accessing or using BikeGrid, you agree to be bound by these Terms of Use. If you do
            not agree, please do not use the site.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">2. BikeGrid is a search engine, not a retailer</h2>
          <p>
            BikeGrid is a search and aggregation service, not a dealership, marketplace, or retailer.
            We do not sell bikes, hold inventory, or act as an intermediary in any transaction. All
            purchases are made directly between you and the relevant bike shop. BikeGrid is not a
            party to any sale and accepts no responsibility for any transaction, product quality,
            fulfilment, or dispute arising from a purchase made through a link on this site.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">3. Information accuracy</h2>
          <p>
            BikeGrid aggregates publicly available product listings from third-party retailers.
            Prices, availability, and discount information are sourced automatically and may not
            reflect current shop inventory at the time of viewing. This information is provided for
            informational purposes only and is not a guarantee of price or availability. Always
            verify pricing and stock directly with the retailer before making a purchase decision.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">4. No warranties</h2>
          <p>
            The site is provided &quot;as is&quot; without warranties of any kind, express or implied.
            BikeGrid makes no representations regarding the completeness, accuracy, or timeliness
            of any information displayed.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">5. Intellectual property</h2>
          <p>
            All brand names, logos, product images, and original listing text displayed on BikeGrid
            remain the property of their respective copyright holders — the original retailers and
            brands. BikeGrid reproduces this material solely to direct users to the original
            source listing and makes no claim of ownership over any third-party content.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">6. External links</h2>
          <p>
            BikeGrid links to external retailer websites. We are not responsible for the content,
            policies, or practices of any third-party site. Clicking through to a retailer and
            making a purchase is solely between you and that retailer.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">7. Affiliate disclosure</h2>
          <p>
            Some links on BikeGrid may be affiliate links. If you click through and make a
            purchase, we may receive a small commission at no additional cost to you. This does not
            influence which products are listed or how they are ranked.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">8. No scraping of BikeGrid</h2>
          <p>
            You may not use automated tools, bots, or scrapers to access, copy, or extract data from
            BikeGrid in bulk. Systematic or automated access to the site or its underlying data
            without prior written permission is prohibited.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">9. Limitation of liability</h2>
          <p>
            To the fullest extent permitted by law, BikeGrid and its operators are not liable for
            any direct, indirect, incidental, or consequential damages arising from your use of the
            site or reliance on information displayed.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">10. Notice and takedown</h2>
          <p>
            If you are a retailer or rights holder and believe that content displayed on BikeGrid
            infringes your rights or you wish to have your listings removed, please{' '}
            <Link to="/contact" className="text-orange-600 hover:underline">contact us</Link> with
            your shop name, the relevant listing URLs, and the reason for your request. We will
            review and action all valid takedown requests promptly.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">11. Changes to terms</h2>
          <p>
            These terms may be updated at any time. Continued use of the site after changes
            constitutes acceptance of the revised terms.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">12. Contact</h2>
          <p>
            Questions about these terms?{' '}
            <Link to="/contact" className="text-orange-600 hover:underline">Get in touch</Link>.
          </p>
        </section>
      </div>
    </div>
  )
}
