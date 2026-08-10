const {
  Document, Packer, Paragraph, TextRun,
  HeadingLevel, AlignmentType,
  BorderStyle, LevelFormat,
  PageNumber, Footer, Header
} = require('docx');

const fs = require('fs');
const path = require('path');

// ---------- COLORS ----------
const NAVY  = "1F3864";
const BLUE  = "2E75B6";
const GRAY  = "595959";
const BLACK = "1A1A1A";
const LBLUE = "D6E4F2";

// ---------- OUTPUT (MAC CURRENT FOLDER SAFE) ----------
const outputPath = path.join(__dirname, "Chapter6_Discussion.docx");

// ---------- HELPERS ----------
function p(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: 360 },
    children: [
      new TextRun({
        text,
        size: 24,
        font: "Times New Roman",
        color: BLACK
      })
    ]
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 120 },
    children: [
      new TextRun({
        text,
        bold: true,
        size: 28,
        font: "Times New Roman",
        color: BLUE
      })
    ]
  });
}

function blockquote(text) {
  return new Paragraph({
    indent: { left: 720 },
    shading: { fill: LBLUE },
    border: {
      left: { style: BorderStyle.SINGLE, size: 8, color: BLUE }
    },
    children: [
      new TextRun({
        text,
        italics: true,
        size: 22,
        font: "Times New Roman",
        color: NAVY
      })
    ]
  });
}

// ---------- DOCUMENT ----------
const doc = new Document({
  sections: [{
    headers: {
      default: new Header({
        children: [
          new Paragraph({
            children: [
              new TextRun({
                text: "Chapter 6: Discussion | Nithin Yadav Gopinath",
                size: 20,
                bold: true,
                color: BLUE
              })
            ]
          })
        ]
      })
    },

    footers: {
      default: new Footer({
        children: [
          new Paragraph({
            children: [
              new TextRun("Page "),
              new TextRun({ children: [PageNumber.CURRENT] })
            ]
          })
        ]
      })
    },

    children: [

      // TITLE
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [
          new TextRun({
            text: "Chapter 6: Discussion",
            bold: true,
            size: 32,
            color: NAVY
          })
        ]
      }),
      // HEADING
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        spacing: { before: 0, after: 160 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: BLUE, space: 8 } },
        children: [new TextRun({ text: "Chapter 6: Discussion", bold: true, size: 32, font: "Times New Roman", color: NAVY })]
      }),

      // 6.1
      h2("6.1 Chapter Overview"),
      p("This chapter situates the experimental findings of Chapter 5 within the broader theoretical, operational, and policy context established in the literature review. Section 6.2 interprets the experimental results in relation to the research question. Section 6.3 addresses the transport-layer versus data-creation-layer distinction as the foundational vulnerability framing of this research. Section 6.4 discusses the implications of observation density as a security variable. Section 6.5 examines the responsible disclosure and dual-use dimensions of this research. Section 6.6 discusses the jurisdictional and data sovereignty complexities specific to space-based observation infrastructure. Section 6.7 situates the findings within the broader space cybersecurity landscape. Section 6.8 acknowledges the principal limitations of this research."),

      // 6.2
      h2("6.2 Interpretation of Findings in Relation to the Research Question"),
      p('This dissertation asked: "How can experimental cybersecurity and integrity assurance mechanisms contribute toward improving resilience within Near-Earth Object tracking data pipelines under simulated adversarial manipulation scenarios?" The experimental results of Chapter 5 provide a direct, quantified answer to this question.'),
      p("The findings demonstrate that adversarial manipulation of ADES-formatted astrometric data \u2014 applied at magnitudes plausibly below existing quality filter thresholds \u2014 produces measurable and operationally significant orbital prediction errors. CAD deltas ranging from 250 km to 5,088 km for Apophis and 494 km to 3,335 km for Bennu represent perturbations of a magnitude that would carry real consequences for planetary defense decision-making, particularly in the context of a genuine close-approach monitoring scenario. The 2029 Apophis flyby, during which the object will pass Earth at approximately 31,860 km \u2014 closer than many operational satellite constellations \u2014 provides a concrete frame of reference: an undetected orbital prediction error of thousands of kilometres at that proximity would meaningfully affect deflection mission planning and public risk communication."),
      p("Critically, these results were achieved without any access to operational systems, classified data, or proprietary infrastructure. All data was sourced from publicly accessible repositories (MPC, JPL Horizons), and all manipulation was performed in a locally isolated simulation environment. This observation carries a dual implication: first, that the research methodology is fully reproducible and ethically bounded; second, and more soberly, that the technical barrier to performing the category of manipulation modelled here is lower than current regulatory and institutional awareness might suggest."),
      p("The research contribution is therefore twofold. Practically, it provides the first empirically grounded quantification of the orbital consequences of adversarial ADES data manipulation. Theoretically, it establishes observation density as a previously uncharacterised security variable in NEO tracking pipelines \u2014 a finding with direct implications for how planetary defense data governance should be structured and prioritised."),

      // 6.3
      h2("6.3 Transport-Layer Security Versus Data-Creation-Layer Integrity"),
      p("A foundational distinction in the security architecture of the NEO tracking pipeline is the difference between transport-layer protection and data-creation-layer integrity assurance. Current MPC submission protocols rely primarily on transport-layer security mechanisms \u2014 specifically TLS (Transport Layer Security) encryption \u2014 to protect observation data during transmission between observing facilities and the MPC\u2019s ingestion systems. While TLS provides robust protection against interception and modification of data in transit, it provides no assurance whatsoever regarding the authenticity or accuracy of the data at the point of its creation."),
      blockquote("Transport-layer security answers the question: 'Was this data modified during transmission?' It cannot answer the question: 'Was this data accurate when it was created?' These are fundamentally different security properties, and only the second is relevant to the threat modelled in this dissertation."),
      p("The ADES standard, as currently specified, does not mandate any cryptographic mechanism for attesting to the provenance or integrity of observation records at the point of creation. There is no digital signature requirement, no hash-based tamper evidence, and no observatory authentication protocol embedded in the ADES format itself. The MPC\u2019s trust model therefore implicitly assumes that any syntactically valid ADES submission from a registered station code is authentic \u2014 an assumption that this research demonstrates to be a structural vulnerability rather than a defensible security posture."),
      p("This vulnerability is not unique to planetary defense. The broader space data architecture exhibits similar patterns: as Khan et al. (2025) document, approximately 50% of GEO satellite signals historically transmitted without strong encryption, and Celik et al. (2023) identify that even the CCSDS Space Data Link Security (SDLS) protocol \u2014 specifically designed for space communication security \u2014 operates at the link layer rather than providing end-to-end data provenance. The gap between transport-layer and data-layer security is therefore systemic across the space information domain, of which the MPC pipeline represents one particularly critical instance."),
      p("The practical implication of this finding is that effective integrity assurance for NEO tracking data requires mechanisms operating at the data creation layer \u2014 specifically, cryptographic provenance schemes that bind observation records to the observing instrument, time of acquisition, and operator identity at the moment of data generation. Blockchain-based provenance ledgers, observatory-level digital signing of ADES records, and distributed consensus verification across multiple independent tracking stations represent candidate architectural approaches, each warranting investigation in future research."),

      // 6.4
      h2("6.4 Observation Density as a Security Variable"),
      p("The finding that observation density functions as a latent security variable in NEO tracking pipelines represents the most novel contribution of this research. The experimental comparison between Apophis and Bennu demonstrates that an identical targeted outlier injection \u2014 20 observations corrupted at 30 arcseconds each \u2014 produces a CAD delta of 250 km for Apophis (0.21% dataset corruption) but 494 km for Bennu (3.32% dataset corruption). The near-doubling of orbital prediction error under identical attack parameters reflects the structural vulnerability of sparse observation corpora to precision targeted attacks."),
      p("This finding has direct policy implications that are not currently addressed in any published planetary defense data governance framework. The MPC quality control infrastructure assesses individual observations against statistical norms derived from the full observation arc. For a well-characterised object like Apophis, with 9,337 observations spanning 17 years, a single corrupted observation is readily isolated as a statistical outlier. For an object like Bennu, with only 603 observations, the same corrupted observation represents a proportionally larger fraction of the orbit determination input, making it correspondingly more influential on the computed orbital solution and more difficult to isolate through statistical means alone."),
      p("Extrapolating this finding to the broader NEO population is instructive. As of 2024, only 42\u201344% of NEOs larger than 140 metres have been catalogued (NASA, 2023). The uncatalogued population, by definition, has sparse or non-existent observation records. As the Vera C. Rubin Observatory\u2019s Legacy Survey of Space and Time (LSST) begins operations and dramatically expands NEO discovery rates, a substantial fraction of newly discovered objects will initially be tracked by only a handful of observatories over short arcs. These newly discovered, sparsely tracked objects are precisely those for which a targeted injection attack would be most effective and hardest to detect \u2014 a convergence of maximum vulnerability and maximum discovery rate that represents a structural risk not currently addressed in planetary defense cybersecurity literature."),
      p("The policy recommendation arising from this finding is clear: data integrity assurance mechanisms should be prioritised and calibrated as a function of observation density, not applied uniformly across all objects. Objects with fewer than a defined threshold number of observations should be subject to enhanced provenance verification requirements, cross-observatory corroboration mandates, and adversarial resilience testing before their orbital solutions are relied upon for hazard assessment decisions."),

      // 6.5
      h2("6.5 Responsible Disclosure and Dual-Use Considerations"),
      p("Any research that demonstrates a previously uncharacterised attack vector against critical infrastructure carries an inherent dual-use tension: the same findings that enable defenders to strengthen a system also provide adversaries with a roadmap for exploitation. This dissertation acknowledges that tension explicitly and addresses it through the following framing."),
      p("First, the research models a category of attack \u2014 astrometric data manipulation \u2014 that requires substantial prior knowledge, sustained access to the observation submission pathway, and the ability to maintain the appearance of legitimate observatory operations over time. This is not a trivial capability. The practical execution of such an attack against operational MPC infrastructure would require overcoming authentication challenges, evading human review processes, and sustaining the deception across multiple observing seasons without triggering quality control flags. The scenarios modelled here represent theoretical upper bounds on attack impact rather than operational instructions."),
      p("Second, this research is conducted entirely within a controlled simulation environment using publicly available data and openly documented tools. No operational systems were accessed, no real observations were modified, and no proprietary data was used. The research therefore falls squarely within the established ethical framework for proof-of-concept security research, consistent with the responsible disclosure norms documented by CISA (2024) for space systems security research."),
      p("Third, and most importantly, the value of this research to defenders substantially outweighs its value to potential adversaries. State-sponsored actors with the capability and motivation to target planetary defense infrastructure would not require academic research to identify the absence of cryptographic provenance in the ADES standard \u2014 this is a publicly documented property of the format specification. What this research provides, uniquely, is a quantified understanding of the consequences of exploitation: specific CAD delta magnitudes, specific vulnerability differentials by observation density, and a structured risk scoring framework that planetary defense agencies can use to prioritise hardening investments. This is precisely the type of empirically grounded intelligence that defenders need and that has previously been absent from the literature."),

      // 6.6
      h2("6.6 Jurisdictional Complexity and Data Sovereignty in Space Observation"),
      p("A dimension of the NEO tracking data integrity problem that extends beyond technical cybersecurity into legal and governance territory concerns the jurisdictional status of space observation data. Astronomical observations are generated by instruments located in multiple countries \u2014 ground-based telescopes, airborne observatories, and space-based platforms \u2014 operating under different national legal frameworks, data governance regimes, and regulatory obligations. The data they generate travels across international network infrastructure before being ingested by the MPC, which is itself hosted by the Smithsonian Astrophysical Observatory in the United States."),
      p("This jurisdictional complexity creates several specific governance gaps relevant to data integrity assurance. The General Data Protection Regulation (GDPR) applies to personal data processed in connection with individuals in the European Union; its territorial scope does not extend to astronomical observation data and provides no relevant framework for astrometric data provenance. The 1967 Outer Space Treaty establishes that space activities must be conducted for the benefit of all countries and prohibits national appropriation of outer space, but is entirely silent on data integrity obligations for ground-based observation infrastructure. No international treaty currently imposes cryptographic provenance requirements on astronomical data submissions."),
      p("The practical consequence is that the legal framework governing NEO observation data integrity is a patchwork of national research data governance policies, voluntary MPC submission guidelines, and observatory-level institutional practices \u2014 none of which were designed with adversarial data manipulation in mind. An observation submitted from a telescope in one jurisdiction, transmitted through network infrastructure in several others, and ingested by an institution in a third jurisdiction creates an attribution and accountability chain of considerable complexity. Determining responsibility for a data integrity failure \u2014 whether accidental or deliberate \u2014 across this chain would present significant legal and investigative challenges under current frameworks."),
      p("This governance gap is not unique to planetary defense. Falco et al. (2022) identify analogous jurisdictional ambiguities in the broader space systems cybersecurity context, noting that the absence of binding international cybersecurity standards for space infrastructure creates structural vulnerabilities that bilateral and multilateral diplomatic frameworks have not yet addressed. The Outer Space Treaty\u2019s prohibition on sovereign appropriation of space \u2014 while foundational \u2014 simultaneously complicates the establishment of clear data governance jurisdiction, since no single state can claim sovereign authority over the observation data pipeline for objects that are, by definition, common global concerns."),
      p("This dissertation does not propose specific legal remedies for these jurisdictional gaps, which fall outside its methodological scope. It does, however, identify them as a necessary complement to technical integrity assurance solutions: cryptographic provenance mechanisms are a necessary but not sufficient condition for securing the NEO data pipeline. Effective security also requires governance frameworks that establish clear accountability, mandatory incident reporting obligations, and internationally coordinated standards for observatory authentication \u2014 frameworks that do not currently exist."),

      // 6.7
      h2("6.7 Situating Findings within the Space Cybersecurity Landscape"),
      p("The findings of this dissertation connect to and extend several strands of existing space cybersecurity research. Khan et al. (2025) established the taxonomy of space information network vulnerabilities and identified the collapse of the barrier to signal interception as a defining characteristic of the current threat landscape. This research extends that analysis by demonstrating that the threat surface extends beyond the link layer to the data layer of the planetary defense pipeline \u2014 a domain that Khan et al. explicitly identify as outside the scope of their analysis."),
      p("Falco et al.\u2019s (2022) SoK framework categorises data integrity attacks as high-consequence and low-detection threats within automated space data pipelines, and identifies the absence of empirical research quantifying orbital consequences as a gap in the literature. This dissertation directly addresses that gap, providing the first simulation-based quantification of ADES data manipulation impact on NEO orbital solutions. The CAD delta magnitudes reported in Chapter 5 give concrete empirical substance to what Falco et al. characterise as a theoretical high-consequence category."),
      p("The 2022 Viasat KA-SAT attack, analysed in detail by Trellix Advanced Research Center (2024), provides the operational precedent that grounds this research in demonstrated real-world adversarial intent. The AcidRain wiper malware\u2019s ability to render tens of thousands of ground terminals inoperable through a coordinated cyber operation demonstrates that adversaries with sufficient motivation and capability will target space-adjacent ground infrastructure when the strategic opportunity arises. The planetary defense data pipeline represents precisely such infrastructure \u2014 global, automated, and currently unprotected at the data layer."),
      p("The GAO\u2019s (2024) finding that NASA cybersecurity practices treat security as an optional consideration across many mission categories provides institutional context for why the vulnerability identified in this research exists and persists. Systemic underinvestment in cybersecurity across space mission acquisition creates an environment in which data-layer vulnerabilities like those demonstrated here can remain unaddressed not through deliberate risk acceptance but through insufficient awareness of the threat."),

      // 6.8
      h2("6.8 Limitations of This Research"),
      p("This research is subject to several limitations that must be acknowledged in interpreting its findings."),
      p("First, the GMAT simulation employs a simplified force model that excludes non-gravitational forces, higher-degree gravity harmonics, and the full planetary ephemeris perturbations used in operational orbit determination. The baseline close approach distances produced by the simulation differ from the published JPL Horizons values for both objects. As stated in Section 5.4.1, this limitation is explicitly designed around: the research focuses on relative CAD deltas between scenarios rather than absolute distance reproduction, and the delta values are internally consistent within the simulation framework. Nevertheless, the precise mapping between simulated deltas and operational orbit determination impact would require validation against a full-fidelity force model in future research."),
      p("Second, the adversarial perturbation magnitudes applied to the geocentric state vectors in the GMAT phase are derived from a simplified analytical model of the relationship between astrometric observation error and orbital state error. A more rigorous treatment would employ a full orbit determination pipeline \u2014 such as OD Toolbox or OpenOrb \u2014 to compute the actual orbital solution from the manipulated observation datasets, rather than approximating the state perturbation analytically. This represents a clear direction for future work."),
      p("Third, the injection archetypes modelled represent three specific classes of adversarial behaviour. More sophisticated attack strategies \u2014 including adaptive injection that modifies observations to be consistent with a specific false orbital solution, or coordinated multi-observatory injection using compromised station codes \u2014 are not modelled. The CAD deltas reported here therefore represent conservative lower bounds on the potential impact of a sophisticated, goal-directed attack."),
      p("Fourth, this research examines only two NEO objects. While Apophis and Bennu were selected for their prominence, well-characterised orbits, and contrasting observation densities, they do not represent the full diversity of NEO orbital types, approach geometries, or tracking histories. Generalising the observation density finding to the broader NEO population requires the caution appropriate to a two-object comparative study."),
      p("Fifth, the CNN-based anomaly detection approach discussed as Objective 3 of this dissertation was evaluated theoretically rather than experimentally, owing to the computational and data preparation requirements of training a reliable detection model within the project timeline. Experimental validation of CNN-based detection represents the primary direction for the next phase of research."),

      // 6.9
      h2("6.9 Summary"),
      p("This chapter has interpreted the experimental findings of Chapter 5 within a broader theoretical and policy context. The central argument of this dissertation \u2014 that the ADES-formatted NEO tracking pipeline is vulnerable to adversarial data manipulation at the data-creation layer, with measurable orbital consequences \u2014 is supported by the quantitative evidence produced in Chapter 5 and contextualised by the analysis in this chapter. The transport-layer versus data-creation-layer distinction identifies the precise architectural gap that integrity assurance mechanisms must address. The observation density finding introduces a new security variable into planetary defense data governance discourse. The responsible disclosure analysis establishes the ethical legitimacy of this research within established security research norms. The jurisdictional analysis identifies the governance complement to technical solutions."),
      p("Taken together, these discussions position this dissertation not merely as a technical exercise in orbital mechanics simulation, but as a contribution to the interdisciplinary field of space infrastructure security \u2014 one that connects astrometric data governance, adversarial cybersecurity, orbital mechanics, and international space law in a way that the existing literature has not previously synthesised.", { italic: false }),

    ]
  }]
});
// ---------- WRITE FILE ----------
const dir = path.dirname(outputPath);
if (!fs.existsSync(dir)) {
  fs.mkdirSync(dir, { recursive: true });
}

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log("DONE →", outputPath);
});
