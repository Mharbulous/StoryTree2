-- Story Tree SQLite Schema v4.4.0 (Story Key Migration)
-- Location: .storytree/local/story-tree.db

-- ID Format: Root="root", Level 1="1","2","3", Level 2+="1.1","1.3.2"
-- story_key: Stable 6-char hex, independent of tree position

CREATE TABLE IF NOT EXISTS story_nodes (
    story_path TEXT PRIMARY KEY,  -- Hierarchical path: "1", "1.2", "1.2.3"
    title TEXT NOT NULL,  -- Story title (aliased as 'feature' in GUI for compatibility)
    description TEXT NOT NULL,
    capacity INTEGER,  -- NULL = dynamic: 3 + implemented/ready children

    -- Three-field workflow system (v4.0, updated v4.3)
    -- Replaces single 'status' column with orthogonal dimensions
    -- Stage values: epic (container) | concept → planning → implementing → testing → releasing → shipped
    -- Legacy aliases preserved for backwards compatibility
    stage TEXT NOT NULL DEFAULT 'concept'
        CHECK (stage IN (
            'epic',  -- Container-only nodes, no workflow progression
            'concept', 'planning', 'implementing', 'testing', 'releasing', 'shipped',
            'approved', 'planned', 'active', 'executing', 'reviewing', 'verifying',
            'implemented', 'ready', 'released', 'polish'  -- Legacy aliases
        )),
    status TEXT DEFAULT 'ready'
        CHECK (status IN (
            'ready', 'queued', 'escalated', 'paused', 'blocked', 'broken', 'polish', 'conflicted', 'wishlisted'
        )),
    terminus TEXT DEFAULT NULL
        CHECK (terminus IS NULL OR terminus IN (
            'rejected', 'infeasible', 'duplicative', 'legacy', 'deprecated', 'archived'
        )),
    human_review INTEGER DEFAULT 0
        CHECK (human_review IN (0, 1)),

    -- Planning stage fields (v4.1)
    user_journeys TEXT,    -- JSON array of user journey descriptions
    dependencies TEXT,     -- JSON array of 3rd-party deps (e.g., ["redis", "stripe-api"])
    prerequisites TEXT,    -- JSON array of story IDs (e.g., ["1.2", "3.1"])
    debug_attempts INTEGER DEFAULT 0,  -- Count of debug ladder attempts (0-5)

    project_path TEXT,
    last_implemented TEXT,
    notes TEXT,
    story_key TEXT UNIQUE NOT NULL,  -- Stable 6-char hex identifier
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    version INTEGER DEFAULT 1  -- For vetting cache invalidation
);

-- Constraint: Cannot have both status != 'ready' AND terminus (status overrides for active holds)
-- Note: SQLite doesn't support ALTER TABLE ADD CONSTRAINT, enforced in app logic

-- Closure table: ALL ancestor-descendant paths
CREATE TABLE IF NOT EXISTS story_paths (
    ancestor_id TEXT NOT NULL REFERENCES story_nodes(story_path) ON DELETE CASCADE,
    descendant_id TEXT NOT NULL REFERENCES story_nodes(story_path) ON DELETE CASCADE,
    depth INTEGER NOT NULL,  -- 0=self, 1=parent/child, 2=grandparent
    PRIMARY KEY (ancestor_id, descendant_id)
);

CREATE TABLE IF NOT EXISTS story_commits (
    story_id TEXT NOT NULL REFERENCES story_nodes(story_path) ON DELETE CASCADE,
    commit_hash TEXT NOT NULL,
    commit_date TEXT,
    commit_message TEXT,
    PRIMARY KEY (story_id, commit_hash)
);

-- Metadata keys: version, lastUpdated, lastAnalyzedCommit
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Vetting decisions cache for Entity Resolution
-- Stores LLM classification decisions to avoid repeated analysis
CREATE TABLE IF NOT EXISTS vetting_decisions (
    pair_key TEXT PRIMARY KEY,  -- Canonical: smaller_id|larger_id
    story_a_id TEXT NOT NULL,
    story_a_version INTEGER NOT NULL,
    story_b_id TEXT NOT NULL,
    story_b_version INTEGER NOT NULL,
    classification TEXT NOT NULL CHECK (classification IN (
        'duplicate', 'scope_overlap', 'competing',
        'incompatible', 'false_positive'
    )),
    action_taken TEXT CHECK (action_taken IN (
        'SKIP', 'DELETE_CONCEPT', 'REJECT_CONCEPT', 'DUPLICATIVE_CONCEPT',
        'BLOCK_CONCEPT', 'TRUE_MERGE', 'PICK_BETTER', 'HUMAN_REVIEW', 'DEFER_PENDING'
    )),
    decided_at TEXT NOT NULL,
    FOREIGN KEY (story_a_id) REFERENCES story_nodes(story_path) ON DELETE CASCADE,
    FOREIGN KEY (story_b_id) REFERENCES story_nodes(story_path) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_paths_descendant ON story_paths(descendant_id);
CREATE INDEX IF NOT EXISTS idx_paths_depth ON story_paths(depth);
CREATE INDEX IF NOT EXISTS idx_commits_hash ON story_commits(commit_hash);
CREATE INDEX IF NOT EXISTS idx_vetting_story_a ON vetting_decisions(story_a_id);
CREATE INDEX IF NOT EXISTS idx_vetting_story_b ON vetting_decisions(story_b_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_story_key ON story_nodes(story_key);

-- Three-field system indexes (v4.0)
CREATE INDEX IF NOT EXISTS idx_active_pipeline ON story_nodes(stage)
    WHERE terminus IS NULL AND status = 'ready';
CREATE INDEX IF NOT EXISTS idx_status ON story_nodes(status)
    WHERE status != 'ready';
CREATE INDEX IF NOT EXISTS idx_terminal_stories ON story_nodes(terminus)
    WHERE terminus IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_needs_review ON story_nodes(human_review)
    WHERE human_review = 1;

-- Triggers
CREATE TRIGGER IF NOT EXISTS story_nodes_updated_at
AFTER UPDATE ON story_nodes
FOR EACH ROW
BEGIN
    UPDATE story_nodes SET updated_at = datetime('now') WHERE story_path = OLD.story_path;
END;

-- =============================================================================
-- THREE-FIELD SYSTEM REFERENCE
-- =============================================================================
--
-- STAGE (7 values + legacy aliases): Linear workflow position
--   epic = Container-only node, no workflow progression (permanent)
--   concept → planning → implementing → testing → releasing → shipped
--
--   LEGACY ALIASES (for backwards compatibility):
--     approved, planned → planning
--     active, executing → implementing
--     reviewing, verifying → testing
--     implemented, ready → releasing
--     released → shipped
--     polish → releasing
--
-- STATUS (9 values): Why work is stopped or condition within stage
--   ready      = No blockers, work can proceed (default)
--   queued     = Waiting for automated processing (algorithm hasn't run yet)
--   escalated  = Human review required
--   paused     = Execution blocked by critical issue
--   blocked    = External dependency
--   broken     = Something wrong with story definition
--   polish     = Needs refinement before proceeding
--   conflicted = Story overlaps scope of another story in inconsistent way
--   wishlisted = Indefinite hold, maybe someday (can be revived when priorities change)
--
-- TERMINUS (6 values + NULL): Terminal state (exits pipeline)
--   NULL        = Active in pipeline
--   rejected    = Human decided not to implement (indicates non-goal)
--   infeasible  = Cannot implement
--   duplicative = Algorithm detected duplicate/overlap with existing story (not a goal signal)
--   legacy      = Old but functional (released only)
--   deprecated  = Being phased out (released only)
--   archived    = No longer relevant
--
-- HUMAN_REVIEW: Boolean flag for items needing human attention
--   Typically TRUE when status != 'ready'
--
-- PLANNING STAGE FIELDS (v4.1):
--   user_journeys  = JSON array of user journey descriptions (from /design-story)
--   dependencies   = JSON array of 3rd-party deps like ["redis", "stripe-api"]
--   prerequisites  = JSON array of story IDs like ["1.2", "3.1"]
--
-- VALID COMBINATIONS:
--   - terminus IS NOT NULL → Story has exited pipeline (stage preserved)
--   - status != 'ready' → Work stopped, but stage shows where to resume
--   - status = 'ready' AND terminus IS NULL → Active in pipeline at given stage
--   - Cannot have BOTH status != 'ready' AND terminus (mutually exclusive)
-- =============================================================================
