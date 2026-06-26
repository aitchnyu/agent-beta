create
can create?
columns

read

update 

delete

Other cols??
SearchContext stuff
No int choice
Magic columns
Ref field - search, link, prefetch
minimize gap

_viewname - how to resolve

Pageerror - fail playwright tests
------------

We are making a class-based crud system. We will make it similar to BaseView-BaseModel.  It will work on child models of FooModel. We are building it step by step, trying to reuse knowledge of BaseView-BaseModel. Create new code, if its ok to reuse code, then reuse.

FooModel (similar to BaseModel, but concrete)
 - created_at
 - public_id - str
 - public_id_generator - default is generate_sequence_id("%Y-%m-%d-ID") - try not to assign values such that leaves gaps when we roll back an insert

Its called FooView. 

We are starting with creating, editing and details. We also have a list page that just shows links of all rows, no pagination.
- /create get 
- /create post
- /update get
- /update post
- list
- /id/<public_id>
- /id/<public_id>/download/<colname>

We define the columns which are engaged with the view like:
```python
class ABCStuff(FooView):
    # it adds some behavior along with model
    columns = {
        'char_field': somemodule.Charfield(editable='createonly'),
        'char_choice_field': somemodule.CharChoicefield(),
        'text_field': somemodule.Textfield(),
        'integer_field': somemodule.Integerfield(),
        'boolean_field': somemodule.Booleanfield(),
        'decimal_field': somemodule.Deciamlfield(),
        'datetime_field': somemodule.Datetimefield(),
        #'ref_field': somemodule.Reffield(),
        'file_field': somemodule.Filefield(editable='createonly'),
    }
```

Its the replacement of include_columns. Smoke test will fail when columns is not defined but we attempt to use it. 

editable can be `createonly`, `never`, or `always`, and latter is default.

We will enable ref field later
-----------
Create 

FirstStuff

prompts/20260624-experimental-class-based-views.md

Do we have csrf protection for api?

When we create a comment, we send notification with content to other subscribers.
ArticleNotification - RowUpdateUserNotification is not generic enough
Add notification count per url
-----------

How to have text search for multiple languages? Set a default language.
`model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')`

## Second guessing
Whole app must become a ninja app, should follow its error handling 

Create and update rows
Send schema to client - send widgets too?

No more user pk leaks, no id for UserProfile

Base model
background color
created by/at
tags?
history

Class views should work with inheritance

How to override stuff? No need to ship everything

How to limit columns to users? Have 2 tiers or tags?

```
    column_names: list[str]
    schemas: th components, td components -- we can override component
    rows: {id, title, columns: {bool:true, int:123}} -- we can add more stuff to columns
    extra: just add this to 
    more_components: 
```

Add view providers - like from tasks to users, search items etc

Kochipython app
submission, approval
Article list
Meetup list and rsvp
Inspection - own activity log

How to group activity logs

How to have invoice - own history, save etc.

No viewname crap. Link explicitly.

Submission - UserProfile, title, abstract, pdf, link
Updates, comments

How to serialize and deserialize?

No central registry of views - each view will direct to others
Have a quick model to contain our existing stuff?

--------
as_html - render proper contents and test them

Is search safe? Can a user find banned objects there

`page_objects = list(page.object_list)` is list[unknown]. Configure mypy to fail if it finds symbols like this. 

Why override components with slots? Just ship props to that place. No more ListRowsContent
FirstStuff Stats - change with new paradigm

const deleteRow
"Image upload failed"

Create and update row should replace browser history

row = cast(Article, context.row)
RowDetailsContext should be generic

Is audit logs supposed to be correct or pretty? Have friendly diffs too.

Why do we have FieldSchema?

models.app should not have ProxyUser

Search - widget just searches existing rows in view

have `model.update_or_404(user, row_id)` instead of  `model.get_row_for_user_and_operation(row_id, user, "update")`

Why are we marking files to delete? Swapping new value could fail.
hardcoded `/tables`
```
      const response = await axios.post(
        `/tables/api/${props.viewname}/upload-article-image/${props.rowId}`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      )
```

Parallel playwright and other speedups?
:class="`row-tr-${row.id}` - avoid them. Have data-row-id="123"

`timeout=` in code
anon_context = self.browser.new_context() - with context
Used in playwright test - `test_details_server_driven_can_edit_can_delete` 
Make a method for `for marked_file in FileMarkedForDeletion.objects.all():`
Not Found: /favicon.ico
Broken pipe from ('127.0.0.1', 55715)

Dirty values - submit only them. Verify its really a change.
Serializers - return str(raw_value).lower() in ("on", "true", "1", "yes")
If form dirty, dont allow to navigate away. Create and edit.
Just fail entire request if a field is malformed, raise a ValueError
Does full_clean catch them all?
datetime_field - always changed. Prevent saving when no changes submitted.

Test page
Escape or back for delete confirm
Notifications - fetch on foregrounding event for any tab
Loading indicators

Prevent overwrite saves - inform user

## Articles
Participant-only articles
Validate article before saving - raise 400
Support image download with nginx
Search - add new widget in top
_URL_FRIENDLY_RE - not international
Cache responses for speed?
Notification when new article published
Author2/co-authors

User ids are handled/leaked by pk
-------

Anon can delete
views - `user = maybe_user(request)`

resolve_columns - can return None. Have a can_create. ResolveContext should have row instead of maybe_row. Send to client.
```python
columns = super().resolve_columns(context)
if columns is None:
    return None
```

```
if context.operation == "create":
    return None
```

No need to resolve columns for delete
get_row_for_user_and_operation - have row_for_read, row_for_update, row_for_delete
row_for_create/update/delete_comment

Have a can_view(user, queryset) which returns queryset of 
Same for can_comment
Notification rules?
Tag previous comments
Seed data - firststuff, articles etc. ArticleEditor user

Simplify context classes
ResolveRowsContext - user, query (QuerySet), operation (one of "create", "read", "update", "delete")
ResolveColumnsContext - user, operation (one of "create", "list", "details", "update", "delete"), columns (tuple of column names), maybe_row (the row instance, for details/update/delete)
SaveContext - user, existing_row, user can be None
CommentPermissionContext - user, operation ("create_comment", "update_comment", "delete_comment"), row
RowUpdateRedactContext - user, row_updates
SearchContext - user, queryset, search_text
NotifyContext - CreateRowNotifyContext, UpdateRowNotifyContext, CreateCommentNotifyContext, UpdateCommentNotifyContext

if resolved_columns is None:
    raise Http404

SaveContext - optional user?

Ergonomics of:
```
ctx: SaveContext[NotifyingFirstStuff] = SaveContext(user=self.user, existing_row=row)  # type: ignore[arg-type]
row.save_stuff(ctx)
```
We should have .create(user) and .update(user). Update docs, with delete too.

-------

Pagination cant exceed 100 or below 5.  
Up button - in details view, send list rows link. Create default object.

Infinite scroll - try to extend page.  

add_titles_to_foreign_key_columns can leak pks

Async task for notifications - generating notifications could be time-consuming

API - have a specific shape of data. Dont directly send widgets from backend. Shapes for create, edit, list, details.  
Resume sending column_schemas with api.

Show inactive user in selects.

## Readme improvements
How to add columns
Add widgets to create and update pages
.save_safely and others

## Custom filters, columns and rendering
Why are our filter even special
columns_raw - no need to send to client if we update filters
Send compatible filters instead of sending column_schemas=column_schemas
disable individual filters and sorting options.  
Facets in left.  
Actions for rows - select them, pass selected to hook component.   
Actions on iframes?   

Whitelist sortable columns
By id, numbers, etc. Certain fields only. Can be overridden.
Dont filter by text columns

have custom filters
sort: -id, id, number, date (no instrospecting?)
query - filter, annotate, sort

----------------------------
Arrange tests
Rich html is part of crud
Files is part of crud
Models and tests - arranged neatly.
Tests with `has-text`

modelname test?
filter_model(type(self)
row.rowupdates - filters by modelname and row
filter methods to model. Now filtering logic is in filters.py.

Inertia upgrade and useHttp

## Maps
Accept areas, lines and point types
Map and calendar in top
Use lazy loading of components

## Notifications and tags
Allow download-file as a href

Comment permalink
File deletion is complete?
CAS for updates

Files in comments?
Track updates for deleted rows, and deleted comments.
Delete updates for deleted row after 2 weeks.
Delete old sessions.
Pg Toast for big text update content?

### Error handling
Ensure no console error messages.

http 400 to show errors
Send 400 error messages from resolve_columns?
Flash for messages
https://inertiajs.com/docs/v2/advanced/error-handling
v3 error handling components

submit forms or submit iframes?
https://inertiajs.com/docs/v2/the-basics/forms#form-context
https://inertiajs.com/docs/v2/the-basics/forms#manual-form-submissions

## Frontend
Change to Zod mini to reduce bundle size?
field.discriminator - split everything into widgets

Check timezone problems
Shorten url. Default pagination - dont assume any from frontend
Remove filters vars from url if empty, client and server side. Remove pagination if default?

## Models
Test permission things with new classes
full_clean called on save

## Future
Child rows   
Quick entry for rows
Date, float columns
Use detailed field name for subtitles or help text
Preload links on hover
Propose changes
Dry run for form validation
Let other users do user crud

## Auth
Disable email and password? Only social.
Have a command that adds SOCIALACCOUNT_PROVIDERS instead of hardcoding
Templates for auth
Test with Telegram and Whatsapp

## Build stuff
Copy paste gate
Pytest?
Mutation testing
    https://github.com/sixty-north/cosmic-ray?tab=readme-ov-file
    https://github.com/boxed/mutmut
    https://mutatest.readthedocs.io/en/latest/
    https://github.com/mutpy/mutpy

## Hosting
Serve media files with nginx or caddy
Use squid or tinyproxy to limit outbound connections
Cheapest - Racknerd+cheap domain, backup from mobile
Managable - Milesweb, Hostineer
Standard - AWS with t4g, RDS
Catch and report backend and frontend errors