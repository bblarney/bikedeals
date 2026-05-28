import { Link } from 'react-router-dom'

export default function PrivacyPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <title>Privacy Policy — BikeDeals</title>
      <meta name="description" content="Read the BikeDeals privacy policy — what data we collect, how we use it, and how we handle your information." />
      <link rel="canonical" href="https://bikedeals.com.au/privacy" />
      <h1 className="text-2xl font-semibold text-slate-900 mb-2">Privacy Policy</h1>
      <p className="text-sm text-slate-400 mb-8">Last updated: May 2026</p>

      <div className="space-y-8 text-slate-600 leading-relaxed text-sm">
        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">1. Overview</h2>
          <p>
            BikeDeals is committed to handling your information transparently. This policy explains
            what data we collect, why we collect it, and how it is used. By using BikeDeals, you
            agree to the practices described here.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">2. What we collect</h2>
          <ul className="list-disc pl-5 space-y-2">
            <li>
              <strong>Usage data:</strong> Pages visited, search filters applied, links clicked, and
              general browsing behaviour on the site, collected via analytics tools.
            </li>
            <li>
              <strong>Device and connection data:</strong> Browser type, device type, operating
              system, and IP address, collected automatically by our hosting and analytics
              infrastructure.
            </li>
            <li>
              <strong>Cookies:</strong> We use cookies to remember preferences (such as your selected
              region) and to support site analytics.
            </li>
            <li>
              <strong>Email addresses (if provided):</strong> If you sign up for deal alerts or
              contact us, we collect the email address you supply.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">3. How we use your data</h2>
          <ul className="list-disc pl-5 space-y-2">
            <li>
              Email addresses are used only to send the alerts or responses you specifically requested.
              We do not sell or share your email address with third parties.
            </li>
            <li>
              Analytics data is used to understand how the site is used and to improve its content
              and performance.
            </li>
            <li>
              We do not build individual user profiles, serve targeted advertising, or sell any
              personal data.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">4. Data we do not collect</h2>
          <p>
            BikeDeals only scrapes public, non-personal product information from retailer websites —
            bike models, prices, specifications, and publicly available images. We explicitly
            filter out and discard any personal identifiers that may appear in source listings,
            such as private seller names, phone numbers, or addresses.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">5. Third-party services</h2>
          <p>
            BikeDeals may use third-party tools such as analytics platforms and hosting providers.
            These services may collect usage data in accordance with their own privacy policies.
            We select providers that meet reasonable data protection standards.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">6. Data retention</h2>
          <p>
            Analytics data is retained only as long as necessary to improve the service. If you
            contact us by email, we retain that correspondence for a reasonable period to handle
            your enquiry.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">7. Your rights</h2>
          <p>
            You may request access to, correction of, or deletion of any personal data we hold about
            you by{' '}
            <Link to="/contact" className="text-blue-600 hover:underline">contacting us</Link>.
            We will respond to all valid requests promptly.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">8. Changes to this policy</h2>
          <p>
            This policy may be updated at any time. Continued use of the site after changes
            constitutes acceptance of the revised policy.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-slate-800 mb-2">9. Contact</h2>
          <p>
            Questions about this policy?{' '}
            <Link to="/contact" className="text-blue-600 hover:underline">Get in touch</Link>.
          </p>
        </section>
      </div>
    </div>
  )
}
