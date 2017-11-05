import copy
import django_filters

from datetime import datetime
from django.http.request import QueryDict
from django.core.exceptions import FieldError
from django.db.models.fields import FieldDoesNotExist

try:
    from django_filters.rest_framework import DjangoFilterBackend
except ImportError:
    # Import for supportable djangorestframework == 3.2.4
    from rest_framework.filters import DjangoFilterBackend

from .utility import cstolist, NoPagination

class ListFilter(django_filters.Filter):
    def filter(self,qs,value):
        if value not in (None,'',[]):
            #convart comma separated str to list
            value = cstolist(value)
            #check is more than one filters are to be applied.
            #This scenerio has been written considering only 'in' query
            #whose performance is quite low as compared to direct matching.
            # Use 'in' query only when multiple filters are to be applied on single fields otherwise direct matching'
            # For other usecases please consider this point in mind before extending
            if len(value)>1:
                return self.get_method(qs)(**{'%s__%s'%(self.name,self.lookup_expr):value})
            else:
                return self.get_method(qs)(**{'%s'%(self.name):value[0]})
        return qs

class ValueListFilter(django_filters.Filter):
    def filter(self,value_list,value):
        validated = all([isinstance(each,dict) for each in value_list])
        if not validated:
            raise Exception('Invalid ValuList. Value list means, list of dictionary, so simple')
        if value not in (None,'',[]):
            value = cstolist(value)
            value_list = filter((lambda x,y=value:x.get(self.name) in y),value_list)
        return value_list

class ValueList(list):
    def __init__(self,value_list):
        self.model = self.__class__
        self.value_list = value_list

    def all(self):
        return self.value_list

    class _meta(object):
        @staticmethod
        def get_field_by_name(*args,**kwargs):
            raise FieldDoesNotExist()
    

class ExcludeListFilter(django_filters.Filter):
    def filter(self,qs,value):
        #import pdb;pdb.set_trace()
        if value not in (None,'',[]):
            #convart comma separated str to list
            value = cstolist(value)
            #check is more than one filters are to be applied.
            #This scenerio has been written considering only 'in' query
            #whose performance is quite low as compared to direct matching.
            # Use 'in' query only when multiple filters are to be applied on single fields otherwise direct matching'
            # For other usecases please consider this point in mind before extending
            if len(value)>1:
                return qs.exclude(**{'%s__%s'%(self.name,self.lookup_type):value})
            else:
                return qs.exclude(**{'%s'%(self.name):value[0]})
        return qs

class CountBackend(object):
    """ Limits the count of result fetched.Use only at the end of filters.Resets the default pagination to NoPagination """
    def filter_queryset(self,request,queryset,view):
        if hasattr(view,'limit_key'):
            countkey = view.limit_key
        else:
            countkey = 'limit'
        limit = request.query_params.get(countkey,None)
        if limit is None or not str(limit).isdigit():
            if not hasattr(view,'limit') or view.limit==-1:
                return queryset
            else:
                limit=view.limit
        view.pagination_class=NoPagination
        if limit == 0:
            return []
        return queryset[:int(limit)]

class ExcludeBackend(object):
    def filter_queryset(self,request,queryset,view):
        exclude_key = getattr(view,'exclude_key','excludekey')
        exclude_val = getattr(view,'exclude_value','excludevalue')
        self.exclude_key = key = request.query_params.get(exclude_key,'id')
        self.exclude_val = values = request.query_params.get(exclude_val)
        if values:
            values = cstolist(values)
            exclude_kwargs = {'{0}__in'.format(key) : values}
            return queryset.exclude(**exclude_kwargs)
        return queryset
    def get_applied_filters(self):
        return {'excluded_{0}'.format(self.exclude_key):self.exclude_val}

class OrderBackend(object):
    def filter_queryset(self,request,queryset,view):
        order_key = getattr(view,'order_key','order')
        order_by_key = getattr(view,'order_by_key','order_by')

        self.order_by_clause = getattr(view,'order_by_clause',{})

        order_by_param = request.query_params.get(order_by_key)

        order_param = request.query_params.get(order_key,'default')
        order_by_tuple = self.get_ordering(order_param)

        if order_by_param:
            ordering = cstolist(order_by_param)
            queryset=queryset.order_by(*ordering)
            self._filters = {order_by_key:order_by_param}

        elif order_by_tuple:
            ordering = order_by_tuple
            queryset = queryset.order_by(*ordering)
            #@TODO Handle ordering for null fields in database
#            if self.field_sort and not "__" in self.field_sort:
#                field_sort = self.field_sort
#                max_value = getattr(queryset.last(),field_sort,None)
#                if max_value and not isinstance(max_value,datetime):
#                    queryset = queryset.extra(select={'ordering':"case when "+ field_sort +" is null then "+str(max_value)+" else " + field_sort + " end"})
#                    queryset = queryset.extra(order_by=['ordering'])
            self._filters = {order_key:order_param}
        else:
            self._filters = {order_key:order_by_param}
        return queryset

    def get_ordering(self,order_param):
        self.field_sort = None
        negative_fn = lambda x:x[1:] if x.startswith('-') else '-'+x
        positive_fn = lambda x:x[1:] if x.startswith('-') else x
        desc_order = True if order_param.startswith('-') else False
        order_param = order_param[1:] if desc_order else order_param
        order_by_tuple = self.order_by_clause.get(order_param,[])
        if desc_order:
            order_by_tuple = map(negative_fn,order_by_tuple)
        if len(order_by_tuple)==1:
            self.field_sort = positive_fn(order_by_tuple[0])
        return order_by_tuple

    def get_applied_filters(self):
        return self._filters

class MutableDjangoFilterBackend(DjangoFilterBackend):
    """
    The default DjangoFilterBackend picks filter from 
    request.query_params which is immutable object. 
    So this has to be used.This filter picks additional params 
    from extra_fargs. Note the use of list object to add additional filter.
    """
    def filter_queryset(self,request,queryset,view):
        filter_class = self.get_filter_class(view, queryset)
        if isinstance(request.query_params,QueryDict):
            fargs = request.query_params.dict()
        else:
            fargs = request.query_params
        if filter_class:
            #in case of related views filter_params is set
            if view.kwargs:
                fargs.update(view.kwargs)
            filterobj=filter_class(fargs, queryset=queryset)
            qs= filterobj.qs
            self.applied_filters = filterobj.form.cleaned_data
            return qs
        return queryset

    def get_applied_filters(self):
        return self.applied_filters
