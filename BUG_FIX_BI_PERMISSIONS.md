# Bug Fix: BI Portal Permissions Not Being Updated

## Problem Description

When a user's BI subcategory permissions were updated in the admin panel, the changes were **not reflected** in the BI Portal. The user would still see dashboards that had been **unselected** after editing their permissions.

### Root Cause

The bug was in `frontend/src/pages/sectors/bi/hooks/useDashboards.ts`. The hook used two separate `useEffect` hooks:

1. **First `useEffect`** (line 35): Fetches dashboards from the server with an **empty dependency array** `[]`
   - This meant the effect would run **only once** when the component mounted
   - Even if user permissions changed, this effect would never run again

2. **Second `useEffect`** (line 171): Monitored changes in user permissions
   - When permissions changed, it would reset internal flags (`hasInitializedRef.current = false`)
   - However, this didn't trigger the first effect to refetch because the first effect had no dependencies

### The Problem Flow

```
1. User logs in → dashboards are fetched and filtered based on their current permissions
2. Admin updates user's BI subcategories
3. useAuth hook detects the change and updates user.bi_subcategories
4. Second useEffect detects the change, but...
5. First useEffect is NOT triggered (empty dependency array!)
6. Dashboards are NOT refetched with the new permissions
7. User sees outdated dashboard list
```

## Solution

The fix consolidates the logic into a **single `useEffect`** with proper dependencies:

```typescript
useEffect(() => {
  // Fetch dashboards whenever user ID or BI subcategories change
  const fetchDashboards = async () => {
    // ... fetch and filter logic ...
  };
  fetchDashboards();
}, [user?.id, user?.bi_subcategories?.join(",")]); // ADDED DEPENDENCIES!
```

### What Changed

1. **Combined two effects into one**: Removed the empty dependency array and the separate monitoring effect
2. **Added proper dependencies**: Now the effect re-runs whenever:
   - `user?.id` changes (user logs out/in)
   - `user?.bi_subcategories?.join(",")` changes (permissions updated)
3. **Removed unnecessary refs**: Cleaned up `hasInitializedRef` which was no longer needed

### Code Changes

**File**: `frontend/src/pages/sectors/bi/hooks/useDashboards.ts`

**Before**:

```typescript
// First effect with empty dependencies - never runs again!
useEffect(() => {
  if (hasInitializedRef.current) return;
  // ... fetch logic ...
  hasInitializedRef.current = true;
}, []);

// Second effect tries to reset, but first effect never runs
useEffect(() => {
  if (user && hasInitializedRef.current) {
    hasInitializedRef.current = false;
    // ...
  }
}, [user?.id, user?.bi_subcategories?.join(",")]);
```

**After**:

```typescript
// Single effect that runs whenever permissions change
useEffect(() => {
  // ... fetch logic ...
}, [user?.id, user?.bi_subcategories?.join(",")]);
```

## Testing the Fix

To verify the fix works:

1. Create or select a user in the TI admin panel
2. Add BI sector to the user's `setores`
3. Mark some BI subcategories (dashboards) for the user
4. Login as that user and navigate to the BI Portal
5. Verify the user sees **only the selected dashboards**
6. Go back to admin panel and **uncheck some dashboards**
7. Refresh the BI Portal (or wait for auto-refresh)
8. **Verify** that the unchecked dashboards are no longer visible ✅

## Impact

- **Fix Type**: Bug fix (no breaking changes)
- **Affected Component**: BI Portal (Portal de BI)
- **User Impact**: Users with restricted BI access will now see correct dashboard filtering after permission updates
- **Performance**: Slightly better - removed unnecessary state checks and refs

## Related Files

- `frontend/src/pages/sectors/bi/hooks/useDashboards.ts` - Fixed hook
- `frontend/src/hooks/useAuth.ts` - User state management
- Backend: `backend/ti/services/users.py` - User permission updates are working correctly
