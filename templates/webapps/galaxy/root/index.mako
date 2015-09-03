<%inherit file="/base.mako"/>
<%namespace file="/galaxy_client_app.mako" import="get_user_dict" />
<%def name="javascripts()">
    ${parent.javascripts()}
    ${h.templates("tool_link", "panel_section", "tool_search")}
</%def>
<%
    ## get configuration
    from markupsafe import escape
    app = trans.app
    app_config = {
        'active_view'               : 'analysis',
        'brand'                     : app.config.get("brand", ""),
        'nginx_upload_path'         : app.config.get("nginx_upload_path", h.url_for(controller='api', action='tools')),
        'use_remote_user'           : app.config.use_remote_user,
        'remote_user_logout_href'   : app.config.remote_user_logout_href,
        'enable_cloud_launch'       : app.config.get_bool('enable_cloud_launch', False),
        'lims_doc_url'              : app.config.get("lims_doc_url", "https://usegalaxy.org/u/rkchak/p/sts"),
        'biostar_url'               : app.config.biostar_url,
        'biostar_url_redirect'      : h.url_for( controller='biostar', action='biostar_redirect', qualified=True ),
        'support_url'               : app.config.get("support_url", "https://wiki.galaxyproject.org/Support"),
        'search_url'                : app.config.get("search_url", "http://galaxyproject.org/search/usegalaxy/"),
        'mailing_lists'             : app.config.get("mailing_lists", "https://wiki.galaxyproject.org/MailingLists"),
        'screencasts_url'           : app.config.get("screencasts_url", "https://vimeo.com/galaxyproject"),
        'wiki_url'                  : app.config.get("wiki_url", "https://wiki.galaxyproject.org/"),
        'citation_url'              : app.config.get("citation_url", "https://wiki.galaxyproject.org/CitingGalaxy"),
        'terms_url'                 : app.config.get("terms_url", ""),
        'allow_user_creation'       : app.config.allow_user_creation,
        'logo_url'                  : h.url_for(app.config.get( 'logo_url', '/')),
        'spinner_url'               : h.url_for('/static/images/loading_small_white_bg.gif'),
        'search_url'                : h.url_for(controller='root', action='tool_search'),
        'is_admin_user'             : trans.user_is_admin(),
        'ftp_upload_dir'            : app.config.get("ftp_upload_dir",  None),
        'ftp_upload_site'           : app.config.get("ftp_upload_site",  None),
        'datatypes_disable_auto'    : app.config.get_bool("datatypes_disable_auto",  False),
        'toolbox'                   : trans.app.toolbox.to_dict( trans, in_panel=False ),
        'toolbox_in_panel'          : trans.app.toolbox.to_dict( trans ),
        'user'          : {
            'requests'  : bool(trans.user and (trans.user.requests or trans.app.security_agent.get_accessible_request_types(trans, trans.user))),
            'email'     : escape( trans.user.email ) if (trans.user) else "",
            'valid'     : bool(trans.user != None),
            'json'      : get_user_dict()
        }
    }
%>
<script>
    require(['mvc/app/app-view'], function(App){
        $(function(){
            Galaxy.config.message_box_class = 'info';
            Galaxy.config.message_box_content = 'sadsadasd';
            var app = new App(${ h.dumps(app_config) });
        });
    });
</script>
