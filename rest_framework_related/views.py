from datetime import datetime
from operator import itemgetter
from collections import OrderedDict

from django.core.urlresolvers import resolve,reverse
from django.http.request import QueryDict
from django.utils.http import is_safe_url
from django.conf import settings
from django.http.response import *

from rest_framework.views import APIView as GAPIView
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework import generics

from .mixins import RelatedView
from .utility import is_ajax
from .py2_3 import *

class ListAPIView(generics.ListAPIView,RelatedView):

    def list(self,request,*args,**kwargs):
        """ 
        Overridden generics.ListAPIView list method to provide additional 
        functionality of related views data fetching and applied filters addition
        """
        response=super(ListAPIView,self).list(request,*args,**kwargs)
        #add applied_filters to the response which is set when filter_queryset method is called
        response=self.addAppliedFilters(response)
        #fetch data from the related views
        return self.fetch_related(request,response,*args,**kwargs)

    def addAppliedFilters(self,response):
        """
        Add the filters applied to the view to response using the view applied_filters attribute accessible with filters key

        """
        if hasattr(self,'applied_filters') and self.applied_filters:
            if not isinstance(response.data,(list,tuple)):
                response.data['filters']=self.applied_filters
        return response

    def filter_queryset(self,queryset):
        """ 
        Overridden generics.ListAPIView filter_queryset method for adding the filters applied to this view.
        Appends filters applied to ListAPIView instance as applied_filters attribute.
        It fetches the filter from filter_backends by calling its get_applied_filters method.
        """

        filters = {}
        for backend in list(self.filter_backends):
            backendobj = backend()
            queryset = backendobj.filter_queryset(self.request, queryset, self)
            if hasattr(backendobj,'get_applied_filters'):
                filters.update(backendobj.get_applied_filters())
        self.applied_filters = OrderedDict()
        from datetime import datetime, date
        for key,value in filters.items():
            if isinstance(value,(datetime,date)):
                self.applied_filters[key]=value
                del filters[key]
        self.applied_filters.update(sorted(filters.items(),key=itemgetter(1),reverse=True))
        return queryset


class RetrieveAPIView(generics.RetrieveAPIView,RelatedView):

    def retrieve(self,request,*args,**kwargs):
        """ 
        Overridden generics.RetrieveAPIView retrieve method to provide additional 
        functionality of related views data fetching
        """
        response=super(RetrieveAPIView,self).retrieve(request,*args,**kwargs)
        return self.fetch_related(request,response,*args,**kwargs)

class APIView(GAPIView,RelatedView):
    """
        Basic View which inherited from APIView which supports only related data fetching and response format support.

    """
    template_name = None
    def get(self,request,*args,**kwargs):
        response = Response({})
        return self.fetch_related(request,response,*args,**kwargs)

class JSONAPIView(APIView):
    renderer_classes = (JSONRenderer,)

class AttachedTabAPIView(RelatedView):
    """
    View attached to a TabAPIView,sharing the same base template.
    """
    def fetch_related(self,request,response,*args,**kwargs):
        response = super(AttachedTabAPIView,self).fetch_related(request,response,*args,**kwargs)
        if getattr(response,'data',None) and getattr(self,'_currenttab',None):
            response.data['current_tab'] = self._currenttab
        return response
    
    
class TabAPIView(RelatedView):
    defaulttab = None
    def fetch_related(self,request,response,*args,**kwargs):
        response = super(TabAPIView,self).fetch_related(request,response,*args,**kwargs)
        if getattr(response,'data',None) and getattr(self,'_currenttab',None):
            response.data['current_tab'] = self._currenttab
        return response

    def get_requested_views(self,request,returnformat):
        """get requested views from request.query_params.relview"""
        if isinstance(request,Request):
            relview_key = getattr(self,'relview_key','relview')
            reqviews = request.query_params.get(relview_key)
            if reqviews is None:
                # if no relview is passed in query_params then fetch
                # from its attribute relview which is set in urls.py
                if self.relview is not None:
                    reqviews = self.relview
            # if related views are not fetched either through query_params
            # or in urls.py and is not jsonrequest then fetch all views
            if reqviews is None: #and returnformat != 'json':
                tabmap = getattr(self,'tabmap',None)
                tabkey = getattr(self,'tab_key','tab')
                if tabmap:
                    currenttab = request.query_params.get(tabkey)
                    if not currenttab:
                        if self.defaulttab is not None:
                            currenttab = self.defaulttab

                    requestedtab = tabmap.get(currenttab,self.defaulttab)
                    if currenttab and requestedtab:
                        reqviews = map(lambda x: x.strip(),requestedtab.strip(',').split(','))
                        self._currenttab = currenttab
            if reqviews:
                return reqviews
        return super(TabAPIView,self).get_requested_views(request,returnformat)
                    
class FormView(APIView,RelatedView):
    def get(self,request,*args,**kwargs):
        self.processRequest(request,*args,**kwargs)
        self.is_get_call=True
        if self.get_form_data():
            last_flow=self._get_last_flow()
            if last_flow['by']==self.view_url_name:
                self._get_last_flow(pop=True)
            return self.postForm(request,*args,**kwargs)
        return self.getForm(request,*args,**kwargs)

    #@method_decorator(csrf_exempt)
    def post(self,request,*args,**kwargs):
        self.is_get_call=False
        self.processRequest(request,*args,**kwargs)
        return self.postForm(request,*args,**kwargs)
    def _get_urlname(self,url):
        urlname= None
        try:
            path=urlparse(url).path
            urlname = resolve(path).url_name
        except:
            pass
        return urlname
    def _get_last_flow(self,pop=False):
        last_flow= None
        flow = self.get_flow()
        if flow:
            if len(flow)>0:
                last_flow =flow[-1] if not pop else flow.pop()
            if len(flow)==0:
                self._destroy_flow(self.request)
        return last_flow

    def _get_current_referer(self,request):
        referer = request.META.get('HTTP_REFERER',None)
        next_url = request.GET.get('next')
        url_name = None
        #if not referer it means its a direct request
        if referer and is_safe_url(url = referer, host=request.get_host()):
            url_name = self._get_urlname(referer)
        if not url_name:
            referer=None
        if next_url:
            url_name,referer = 'homepage',next_url
        return (url_name,referer)


    def redirect_to(self,url,data={}):
        if is_ajax(self.request):
            resdata = {'location':url}
            resdata.update(data)
            return Response(resdata)
        return Response({},status=302,headers={'Location':url})

    def send_next(self,name,packet=None,query_dict={},returnurl=True,finalurl=None,data={}):
        """
        sends to next page maintaing history in session.
        - name : Name of the form view to be sent next without _form_view
        - packet : packet to be transferred to next form view
        - query_dict : query parameter to be passed
        - returnurl :
            True - return back to this view once the job has been done
            False - No need to return here just continue with normal flow
            <urlstr> - send to urlstr once the job finished. It must be a form_view url
        - finalurl - the final url to send.it resets the whole flow

        """
        view_url = name + '_form_view'
        try:
            urlpath = reverse(view_url)
            query_dict.update({'_caller':self.view_url_name})
            url = urlpath + '?'+ urlencode(query_dict)
        except:
            #@TODO need to clean every session data here
            url = reverse('homepage')
        if packet and isinstance(packet,dict):
            packet['to']=view_url
            self.request.session['_packet']=packet

        if finalurl:
            self._initiate_flow(self.request,finalurl) 
        elif returnurl == True:
            self._addurl(self._get_current_url())
        elif returnurl != False:
            self._addurl(returnurl)

        return self.redirect_to(url,data)

    def send_back(self,packet=None,data={},query_dict={}):
        obj = self._get_last_flow(pop=True)
        if obj:
            is_last = not self.get_flow()
            redirect_url = obj['url']
            if not is_last:
                query_dict.update({'_caller':self.view_url_name})
                if packet and isinstance(packet,dict):
                    packet['to']=self._get_urlname(redirect_url)
                    self.request.session['_packet']=packet
            redirect_url = self.get_query_url(redirect_url,query_dict)
            return self.redirect_to(redirect_url,data)
        return self.redirect_to(reverse('homepage'),data)

    def get_query_url(self,current_path,query_params={}):
        join_char = '&' if urlparse(current_path).query else '?'
        query_url = current_path + join_char + urlencode(query_params)
        return query_url
 
    def get_view_cache(self,key=None,pop=False):
        if not key:
            return self._sessdata
            
        data = self._sessdata.get(key,None)
        if pop:
            self.set_view_cache(key,None)
        return data


    def set_view_cache(self,key,data=None):
        if not key:
            raise Exception('Key is mandatory for setting form view cache')
        if data is None:
            self._sessdata.pop(key,None)
        else:
            self._sessdata[key]=data
        self.request.session[self.view_url_name]=self._sessdata
        return True

    def set_form_data(self,data):
        return self.set_view_cache('_formdata',data)

    def get_form_data(self):
        if not hasattr(self,'_formdata'):
            self._formdata=self.get_view_cache('_formdata')
        return self._formdata

    def get_caller(self):
        return self._caller

    def get_packet(self):
        return self._packet
    def get_flow(self):
        return self.request.session.get('_formflow',None)

    def _addurl(self,url):
        formflow = self.request.session.get('_formflow',[])
        #@TODO Remove it from here
        if not formflow:
            self._initiate_flow(self.request,withurl='/')
            formflow = self.request.session.get('_formflow',[])
            #raise Exception('_addurl called before initiating the flow')
        formflow.append({'by':self.view_url_name,'url':url})
        self.request.session['_formflow']=formflow
        return True

    def _destroy_flow(self,request):
        sess=request.session
        keys = request.session.keys()
        #@TODO check if these deletions are making multiple db hits
        if '_packet' in keys:
            del sess['_packet']
        if '_formflow' in keys:
            del sess['_formflow']
        for key in keys:
            if key.endswith('_form_view'):
                del sess[key]


    def _initiate_flow(self,request,withurl=None):
        self._destroy_flow(request)
        sess=request.session
        if not withurl:
            withurl = settings.LOGIN_REDIRECT_URL
        sess['_formflow']=[{'by':'initiator','url':withurl}]
        return True
    def _get_current_url(self):
        return reverse(self.view_url_name)

    def processRequest(self,request,*args,**kwargs):
        keyname = self.view_url_name
        self._caller = None
        self._packet = {}
        caller = request.query_params.get('_caller',False)
        #check if called from another view
        if caller:
            packet = request.session.get('_packet',{})
            #@TODO what to do if packet is not found
            # Is this invalid packet?
            if packet.get('to',None) == keyname:
                self._packet = packet
                request.session.pop('_packet',None)
            self._caller = caller
        else:
            url_name,referer = self._get_current_referer(request)
            if not referer:
                #@TODO A case when user refreshes the page the referer is not set in which get this gets called.Need to fix it later
                self._initiate_flow(request)
            else:
                if url_name == self.view_url_name:
                    #it is a request from its post form
                    pass
                elif url_name.endswith('_form_view'):
                    #the flow is broken and the user has switched to other flow
                    pass
                else:
                    self._initiate_flow(request,withurl=referer)
                    #it means urls in session are valid
        self._sessdata = request.session.get(keyname,{})

    def call_get(self,request,*args,**kwargs):
        if is_ajax(request):
            return Response(kwargs)
        return self.getForm(request,*args,**kwargs)

