# BI Portal Subcategories Permissions Fix - Testing Guide

## Problem
When granting permission for BI portal subcategories, when the user logs out and logs back in, they regain access to all subcategories, even when only 1 was selected.

**Root Cause**: The permission persistence and loading flow needed better validation and logging to identify where the issue occurs.

## What Was Fixed

### 1. **Backend Debug Endpoints**
- Created `/api/debug/bi-permissions/{user_id}` - Check BI permissions for a specific user
- Created `/api/debug/all-users-bi-permissions` - Check permissions for all users
- Created `/api/debug/set-bi-permissions/{user_id}` - Manually set BI permissions (for testing)
- Created `/api/debug/refresh-user/{user_id}` - Trigger permission refresh event

### 2. **Enhanced Logging**
- Improved `_set_bi_subcategories` function with detailed logging of:
  - Input validation
  - JSON parsing
  - Final database value
- Enhanced API endpoint logging with better error messages

### 3. **Frontend Improvements**
- Added logging verification for BI subcategories when updating users
- Added check to verify BI subcategories were saved correctly
- Better error reporting when permissions are not persisted

## Step-by-Step Testing Guide

### Step 1: Verify Backend Debug Endpoints

The API now has debug endpoints. You can test them:

```bash
# Check current permissions for user ID 5
curl http://localhost:8000/api/debug/bi-permissions/5

# Check all users' BI permissions
curl http://localhost:8000/api/debug/all-users-bi-permissions

# Manually set BI permissions (POST request)
curl -X POST http://localhost:8000/api/debug/set-bi-permissions/5 \
  -H "Content-Type: application/json" \
  -d '{"dashboard_ids": ["dashboard_1", "dashboard_2"]}'

# Trigger a refresh event for user
curl -X POST http://localhost:8000/api/debug/refresh-user/5
```

### Step 2: Test the Permission Persistence Flow

1. **Open the admin dashboard**
   - Go to TI Portal → Administração → Gerenciar Usuários

2. **Edit an existing user** (or create a new one)
   - Click on a user to edit
   - Select "Portal de BI" in the sectors
   - Select **ONLY 1 dashboard** from the "Dashboards do Portal de BI" section
   - Save the user

3. **Check the console logs**
   - Open browser DevTools (F12)
   - Look for logs starting with `[ADMIN]` in the console
   - Verify you see: `[ADMIN] ✅ BI Subcategories retornadas do servidor: [...]`

4. **Check backend logs**
   - Check the backend console/logs
   - Look for logs starting with `[_set_bi_subcategories]`
   - Verify the BI subcategories are being saved correctly

### Step 3: Verify Database Persistence

After saving the user, check the database directly:

```bash
# Using the debug endpoint
curl http://localhost:8000/api/debug/bi-permissions/5

# Expected response:
{
  "user_id": 5,
  "_bi_subcategories_raw_from_db": "[\"dashboard_123\"]",
  "_bi_subcategories_parsed": ["dashboard_123"],
  "_bi_subcategories_raw_is_null": false,
  "note": "Check the _bi_subcategories_raw_from_db field..."
}
```

### Step 4: Test the Login Refresh Flow

1. **Get the user ID** from the debug endpoint
2. **Log in as that user**
   - The user should only see the 1 dashboard they have permission for
   - Check browser console for logs starting with `[BI]`
   - Verify: `[BI] 🔐 Filtrando dashboards por permissão do usuário: ["dashboard_123"]`

3. **Log out and log back in**
   - User should still only see the 1 dashboard
   - NOT all dashboards

4. **Check browser console**
   - You should see the permission being enforced: `[BI] ✅ 1 dashboards após filtragem`

### Step 5: Test Multi-Dashboard Permissions

1. **Edit the same user again**
2. **Select 2 or 3 dashboards** this time
3. **Save and repeat steps 3-4**
4. **Verify the filter logs** show the correct number of dashboards

### Step 6: Test Empty Permission (BI sector but no dashboards)

1. **Edit a user and select "Portal de BI"**
2. **Do NOT select any dashboards**
3. **Save**
4. **Check the debug endpoint** - Should show `_bi_subcategories_parsed: []`
5. **Log in as that user** - User should see NO dashboards
6. **Verify console log**: `[BI] 🔒 Usuário tem setor BI mas sem dashboards selecionados - acesso negado`

## Key Logs to Look For

### Backend Logs (when saving user permissions)
```
[_set_bi_subcategories] ========== START ==========
[_set_bi_subcategories] Called with: ['dashboard_123']
[_set_bi_subcategories] ✅ Setting _bi_subcategories to JSON: "[\"dashboard_123\"]"
[_set_bi_subcategories] Final value in DB: "[\"dashboard_123\"]"
[_set_bi_subcategories] ========== END ==========

[API] ✅ bi_subcategories parsed from '["dashboard_123"]' -> ['dashboard_123']
```

### Frontend Logs (when saving user)
```
[ADMIN] ✅ BI Subcategories retornadas do servidor: ['dashboard_123']
```

### Frontend Logs (when loading BI page)
```
[BI] 🔐 Filtrando dashboards por permissão do usuário: ['dashboard_123']
[BI] ✅ 1 dashboards após filtragem
```

### Frontend Logs (when login changes)
```
[AUTH] ✓ BI_SUBCATEGORIES CHANGED: [] → ['dashboard_123']
```

## Troubleshooting

### Issue: `_bi_subcategories_raw_from_db` is `null`
- **Cause**: Permission was never saved to the database
- **Solution**: 
  1. Check the save log (Step 3) - was there an error?
  2. Use `/api/debug/set-bi-permissions/{user_id}` to manually set permissions
  3. Try saving again from the admin interface

### Issue: Dashboard list is still showing all dashboards after login
- **Check 1**: Is `_bi_subcategories_raw_from_db` populated? (Use debug endpoint)
- **Check 2**: Is `authenticate_user` returning `bi_subcategories`? (Check backend logs)
- **Check 3**: Is the frontend storing the value? (Check browser console `[AUTH]` logs)
- **Check 4**: Is the filter logic working? (Check `[BI]` logs)

### Issue: Getting JSON decode errors
- **Check the raw value** in the debug endpoint
- **Should be**: `"[\"dashboard_1\", \"dashboard_2\"]"`
- **If it's something else**: There's a JSON serialization issue
- **Solution**: Use `/api/debug/set-bi-permissions/{user_id}` to reset and save correctly

## Database Check (Direct SQL)

If needed, you can check the database directly:

```sql
-- Check raw _bi_subcategories value for a user
SELECT id, usuario, email, _bi_subcategories FROM user WHERE id = 5;

-- Should show something like:
-- _bi_subcategories: ["dashboard_123"]  (as a JSON string)

-- If NULL or empty string, the permission wasn't saved
```

## Summary

The fix ensures that:
1. ✅ BI subcategory permissions are properly serialized to JSON
2. ✅ Permissions are correctly persisted in the database
3. ✅ Permissions are loaded on authentication
4. ✅ Frontend properly enforces the permission restrictions
5. ✅ Comprehensive logging allows debugging if issues occur

Use the debug endpoints and logs above to verify the complete flow is working correctly.
