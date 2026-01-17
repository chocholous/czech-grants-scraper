// actors/mzd-actor/src/main.js
const { Actor, Input } = require('apify');
const { CheerioCrawler, ProxyConfiguration } = require('crawlee');

// Define PRD output schema structure for data validation (simplified here)
const OUTPUT_SCHEMA = {
    actorOutputSchemaVersion: 1,
    title: "MZD Grant Output",
    properties: {
        recordType: { type: 'string' },
        sourceName: { type: 'string' },
        title: { type: 'string' },
        deadline: { type: 'string' },
        fundingAmount: { type: 'object' },
        status: { type: 'string' },
        contentHash: { type: 'string' },
        // Add other required fields from PRD here
    }
};

async function main() {
    await Actor.init();

    const input = await Input.getValue();
    const { proxyConfiguration, startUrls = [] } = input;

    // Simple input validation check
    if (!startUrls || startUrls.length === 0) {
        Actor.log.error('Input missing: startUrls is required.');
        await Actor.exit(1);
        return;
    }

    const proxy = proxyConfiguration ? new ProxyConfiguration(proxyConfiguration) : undefined;

    const crawler = new CheerioCrawler({
        proxyConfiguration: proxy,
        useSessionPool: true,
        maxRequestsPerMinute: 50,
        requestHandler: async ({ request, page, cheerio, log }) => {
            const { url } = request;
            log.info(`Processing URL: ${url}`);

            // --- Step 1: Determine if this is a listing page or a detail page ---
            // We will refine this logic after research. For now, assume everything is a detail page template.
            
            const grantData = await extractGrantData(url, cheerio, log);
            
            if (grantData) {
                // Assume we push data directly for this MVP
                await Actor.pushData(grantData);
                log.info(`Successfully extracted grant: ${grantData.title}`);
            } else {
                log.warning(`Could not extract grant data from: ${url}`);
            }
        },
        // Add a handler for links/pagination if needed later
    });

    await crawler.run(startUrls);
    
    Actor.log.info('MZD Scrape finished.');
    await Actor.exit();
}

/**
 * Placeholder function for extracting grant data from a page.
 * This will be implemented after research confirms the structure.
 */
async function extractGrantData(url, cheerio, log) {
    // Mock data structure conforming to PRD for initial commit
    log.debug(`Analyzing structure for: ${url}`);

    // In a real scenario, we'd check if it's a list page and enqueue details,
    // or if it's a detail page, extract structured data.
    
    return {
        recordType: "grant",
        sourceId: "mzd_gov_cz_2026",
        sourceName: "MZD Národní grantové programy 2026",
        sourceUrl: "https://mzd.gov.cz/category/dotace-a-programove-financovani/narodni-dotacni-programy-2026/",
        grantUrl: url,
        title: `Mock Grant Title from ${url.substring(0, 40)}...`,
        summary: "Placeholder summary.",
        description: "Placeholder description.",
        eligibility: ["Mock Eligibility"],
        fundingAmount: { min: 100000, max: 500000, currency: "CZK" },
        deadline: "2026-12-31", // Mock date
        status: "ok",
        statusNotes: "Initial structure placeholder",
        extractedAt: new Date().toISOString(),
        contentHash: "mockhash123"
    };
}

main();
