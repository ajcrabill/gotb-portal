export default function Footer() {
  const ESB_SITE = "https://effectiveschoolboards.com";

  return (
    <footer id="footer">
      {/* Top dark-blue section */}
      <div
        style={{
          background: "var(--esb-section-dark)",
          padding: "60px 0 30px",
          color: "#fff",
        }}
      >
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {/* Brand */}
            <div>
              <h3
                style={{
                  fontFamily: "var(--font-logo)",
                  fontSize: "22px",
                  fontWeight: 600,
                  marginBottom: "16px",
                }}
              >
                Effective{" "}
                <span style={{ color: "var(--esb-primary)" }}>School Boards</span>
              </h3>
              <p style={{ color: "#aaaaaa", fontSize: "14px", lineHeight: "1.7" }}>
                Supporting school boards in becoming Great on Their Behalf — focused
                on student outcomes and effective governance.
              </p>
            </div>

            {/* For School Systems */}
            <div>
              <h4
                style={{
                  fontFamily: "var(--font-heading)",
                  fontSize: "16px",
                  fontWeight: 700,
                  marginBottom: "16px",
                  paddingBottom: "12px",
                  borderBottom: "2px solid var(--esb-primary)",
                  display: "inline-block",
                }}
              >
                For School Systems
              </h4>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {[
                  ["The Great on Their Behalf Index", "/portal/assessment"],
                  ["Certified Assessment", "/portal/assessment?tier=certified"],
                  ["Implementation Plan", "/plan"],
                  ["Find a Practitioner", `${ESB_SITE}/coaches/find/`],
                ].map(([label, href]) => (
                  <li key={label} style={{ marginBottom: "8px" }}>
                    <a
                      href={href}
                      style={{
                        color: "#aaaaaa",
                        textDecoration: "none",
                        fontSize: "14px",
                        transition: "color 0.3s",
                      }}
                      className="hover:text-white"
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            {/* For Practitioners */}
            <div>
              <h4
                style={{
                  fontFamily: "var(--font-heading)",
                  fontSize: "16px",
                  fontWeight: 700,
                  marginBottom: "16px",
                  paddingBottom: "12px",
                  borderBottom: "2px solid var(--esb-primary)",
                  display: "inline-block",
                }}
              >
                For Practitioners
              </h4>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {[
                  ["IRR Simulator", "/portal/irr-simulator"],
                  ["My Clients", "/portal/clients"],
                  ["Become a Practitioner", `${ESB_SITE}/coaches/become/`],
                  ["Certification", `${ESB_SITE}/coaches/senior/`],
                ].map(([label, href]) => (
                  <li key={label} style={{ marginBottom: "8px" }}>
                    <a
                      href={href}
                      style={{
                        color: "#aaaaaa",
                        textDecoration: "none",
                        fontSize: "14px",
                        transition: "color 0.3s",
                      }}
                      className="hover:text-white"
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            {/* Resources */}
            <div>
              <h4
                style={{
                  fontFamily: "var(--font-heading)",
                  fontSize: "16px",
                  fontWeight: 700,
                  marginBottom: "16px",
                  paddingBottom: "12px",
                  borderBottom: "2px solid var(--esb-primary)",
                  display: "inline-block",
                }}
              >
                Resources
              </h4>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {[
                  ["ESB Framework", `${ESB_SITE}/framework/`],
                  ["Glossary", `${ESB_SITE}/resources/glossary/`],
                  ["Community", `${ESB_SITE}/community/`],
                  ["Contact", `${ESB_SITE}/contact/`],
                ].map(([label, href]) => (
                  <li key={label} style={{ marginBottom: "8px" }}>
                    <a
                      href={href}
                      style={{
                        color: "#aaaaaa",
                        textDecoration: "none",
                        fontSize: "14px",
                        transition: "color 0.3s",
                      }}
                      className="hover:text-white"
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom black strip */}
      <div
        style={{
          background: "var(--esb-footer-bg)",
          padding: "20px 0",
          color: "#aaaaaa",
        }}
      >
        <div
          className="container mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-2"
          style={{ fontSize: "14px" }}
        >
          <div>
            &copy; {new Date().getFullYear()} Effective School Boards. All rights reserved.
          </div>
          <div className="flex gap-4">
            <a href={`${ESB_SITE}/privacy/`} style={{ color: "#aaaaaa" }} className="hover:text-white">
              Privacy
            </a>
            <a href={`${ESB_SITE}/terms/`} style={{ color: "#aaaaaa" }} className="hover:text-white">
              Terms
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
